"""FastAPI upload app for Alpha-Audit.

Upload a trading journal PDF, extract rows, organize them into trade cycles,
then run the existing OpenRouter analysis pipeline.
"""

from __future__ import annotations

import html
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from src.analyzer import analyze_organized_file
from src.extractor import extract_pdf
from utils.organizer import organize

APP_DIR = Path(__file__).resolve().parent
RUNS_DIR = APP_DIR / "runs"

app = FastAPI(title="Alpha-Audit", version="0.1.0")


def _escape(value: Any) -> str:
    return html.escape("") if value is None else html.escape(str(value))


def _render_page(
    *,
    error: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> HTMLResponse:
    summary_cards = ""
    mistakes_rows = ""
    download_links = ""

    if result:
        summary_cards = f"""
        <section class=\"grid\">
          <div class=\"card metric\"><span>Model</span><strong>{_escape(result.get('model', '—'))}</strong></div>
          <div class=\"card metric\"><span>Generated</span><strong>{_escape(result.get('generated_at', '—'))}</strong></div>
          <div class=\"card metric\"><span>Symbols</span><strong>{len(result.get('results') or [])}</strong></div>
          <div class=\"card metric\"><span>Source</span><strong>{_escape(result.get('source_organized', '—'))}</strong></div>
        </section>
        """

        rows: List[Dict[str, Any]] = []
        for block in result.get("results") or []:
            symbol = block.get("symbol", "?")
            if block.get("error"):
                rows.append(
                    {
                        "symbol": symbol,
                        "severity": "high",
                        "title": "Analysis error",
                        "evidence": block.get("error", ""),
                        "suggestion": "Check your API key, model name, or PDF parsing output.",
                    }
                )
            else:
                for mistake in block.get("mistakes") or []:
                    rows.append(
                        {
                            "symbol": symbol,
                            "severity": mistake.get("severity", ""),
                            "title": mistake.get("title", ""),
                            "evidence": mistake.get("evidence", ""),
                            "suggestion": mistake.get("suggestion", ""),
                        }
                    )

        if rows:
            mistakes_rows = "\n".join(
                "<tr>"
                f"<td>{_escape(row['symbol'])}</td>"
                f"<td><span class='pill'>{_escape(row['severity'])}</span></td>"
                f"<td>{_escape(row['title'])}</td>"
                f"<td>{_escape(row['evidence'])}</td>"
                f"<td>{_escape(row['suggestion'])}</td>"
                "</tr>"
                for row in rows
            )
        else:
            mistakes_rows = "<tr><td colspan='5' class='muted'>No mistakes reported by the model.</td></tr>"

        run_dir = Path(result.get("run_dir", ""))
        if run_dir and run_dir.is_dir():
            download_links = f"""
            <div class=\"downloads\">
              <a href=\"/artifact/{run_dir.name}/analysis\">Download analysis JSON</a>
              <a href=\"/artifact/{run_dir.name}/organized\">Download organized JSON</a>
              <a href=\"/artifact/{run_dir.name}/processed\">Download processed JSON</a>
            </div>
            """

    body = f"""
    <!doctype html>
    <html lang=\"en\">
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>Alpha-Audit</title>
        <style>
          :root {{
            --bg: #0b1020;
            --panel: rgba(13, 19, 39, 0.86);
            --panel-strong: rgba(17, 26, 51, 0.95);
            --border: rgba(255, 255, 255, 0.10);
            --text: #e8edf7;
            --muted: #97a3bd;
            --accent: #7dd3fc;
            --shadow: 0 30px 80px rgba(0, 0, 0, 0.32);
          }}
          * {{ box-sizing: border-box; }}
          body {{
            margin: 0;
            min-height: 100vh;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: var(--text);
            background:
              radial-gradient(circle at top left, rgba(125, 211, 252, 0.18), transparent 32%),
              radial-gradient(circle at top right, rgba(245, 158, 11, 0.16), transparent 28%),
              linear-gradient(180deg, #050816 0%, #0b1020 45%, #0a0f1c 100%);
          }}
          .wrap {{ max-width: 1180px; margin: 0 auto; padding: 40px 20px 56px; }}
          .hero {{
            display: grid;
            gap: 16px;
            grid-template-columns: 1.25fr 0.75fr;
            align-items: start;
            margin-bottom: 24px;
          }}
          .hero h1 {{ margin: 0; font-size: clamp(2.1rem, 4vw, 4.4rem); line-height: 0.95; letter-spacing: -0.05em; }}
          .hero p {{ margin: 0; max-width: 64ch; color: var(--muted); font-size: 1.03rem; line-height: 1.65; }}
          .eyebrow {{
            display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px;
            border: 1px solid var(--border); border-radius: 999px; background: rgba(255,255,255,0.04);
            color: var(--muted); font-size: 0.85rem; letter-spacing: 0.08em; text-transform: uppercase;
          }}
          .card {{
            border: 1px solid var(--border); border-radius: 22px; background: var(--panel);
            box-shadow: var(--shadow); backdrop-filter: blur(16px);
          }}
          .form-card {{ padding: 24px; }}
          form {{ display: grid; gap: 16px; }}
          label {{ display: grid; gap: 8px; font-size: 0.95rem; color: var(--muted); }}
          input[type=\"file\"], input[type=\"text\"], input[type=\"password\"] {{
            width: 100%; padding: 14px 14px; border: 1px solid var(--border); border-radius: 14px;
            background: rgba(255, 255, 255, 0.04); color: var(--text);
          }}
          input::placeholder {{ color: #73809b; }}
          .actions {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }}
          button {{
            appearance: none; border: 0; border-radius: 14px; padding: 14px 18px;
            background: linear-gradient(135deg, var(--accent), #a78bfa); color: #04111f;
            font-weight: 700; cursor: pointer;
          }}
          .hint {{ color: var(--muted); font-size: 0.92rem; }}
          .error {{ margin: 18px 0 0; padding: 14px 16px; border-radius: 14px; background: rgba(248, 113, 113, 0.12); border: 1px solid rgba(248, 113, 113, 0.30); color: #ffd2d2; }}
          .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 24px 0; }}
          .metric {{ padding: 18px; background: var(--panel-strong); }}
          .metric span {{ display: block; color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; }}
          .metric strong {{ display: block; margin-top: 10px; font-size: 1rem; line-height: 1.35; word-break: break-word; }}
          .section {{ margin-top: 26px; }}
          .section h2 {{ margin: 0 0 14px; font-size: 1.25rem; }}
          .table-wrap {{ overflow-x: auto; border-radius: 18px; border: 1px solid var(--border); background: rgba(255,255,255,0.03); }}
          table {{ width: 100%; border-collapse: collapse; min-width: 820px; }}
          th, td {{ padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: left; vertical-align: top; }}
          th {{ color: #c7d2e8; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; background: rgba(255,255,255,0.04); }}
          td {{ color: #e6ebf6; }}
          .pill {{
            display: inline-flex; align-items: center; padding: 6px 10px; border-radius: 999px;
            background: rgba(125, 211, 252, 0.10); color: #b9efff; font-size: 0.82rem;
          }}
          .muted {{ color: var(--muted); }}
          .downloads {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 18px 0 0; }}
          .downloads a {{
            color: #dbf4ff; text-decoration: none; padding: 10px 14px; border: 1px solid var(--border);
            border-radius: 12px; background: rgba(255,255,255,0.04);
          }}
          @media (max-width: 900px) {{
            .hero, .grid {{ grid-template-columns: 1fr; }}
          }}
        </style>
      </head>
      <body>
        <div class=\"wrap\">
          <section class=\"hero\">
            <div>
              <div class=\"eyebrow\">Alpha-Audit / Trading Journal Analyzer</div>
              <h1>Upload a PDF and start analyzing your trade journal.</h1>
              <p>
                This local web app extracts rows from a Binance-style PDF, groups them into trade cycles,
                and sends the organized data to your selected OpenRouter model for execution review.
              </p>
            </div>
            <div class=\"card form-card\">
              <strong style=\"display:block;font-size:1rem;margin-bottom:8px;\">Pipeline</strong>
              <div class=\"muted\" style=\"line-height:1.7;\">
                1. Upload PDF<br />
                2. Extract trade rows<br />
                3. Organize cycles<br />
                4. Analyze mistakes
              </div>
            </div>
          </section>

          <section class=\"card form-card\">
            <form action=\"/analyze\" enctype=\"multipart/form-data\" method=\"post\">
              <label>
                Trading journal PDF
                <input accept=\"application/pdf\" name=\"pdf_file\" type=\"file\" required />
              </label>
              <label>
                OpenRouter API key
                <input name=\"api_key\" type=\"password\" placeholder=\"Use your .env key or paste one here\" />
              </label>
              <label>
                Model
                <input name=\"model\" type=\"text\" value=\"openai/gpt-4o-mini\" />
              </label>
              <div class=\"actions\">
                <button type=\"submit\">Analyze PDF</button>
                <span class=\"hint\">Large PDFs may take a minute while the model reviews each symbol.</span>
              </div>
            </form>
            {f'<div class="error">{_escape(error)}</div>' if error else ''}
          </section>

          {summary_cards}
          {download_links}

          <section class=\"section\">
            <h2>Mistakes</h2>
            <div class=\"table-wrap\">
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Severity</th>
                    <th>Title</th>
                    <th>Evidence</th>
                    <th>Suggestion</th>
                  </tr>
                </thead>
                <tbody>
                  {mistakes_rows or "<tr><td colspan='5' class='muted'>Upload a PDF to generate analysis results.</td></tr>"}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(body)


def _save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as target:
        shutil.copyfileobj(upload.file, target)


def _load_analysis(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return _render_page()


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    pdf_file: UploadFile = File(...),
    api_key: str = Form(""),
    model: str = Form("openai/gpt-4o-mini"),
) -> HTMLResponse:
    if not pdf_file.filename:
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    if not pdf_file.filename.lower().endswith(".pdf"):
        return _render_page(error="Please upload a .pdf file.")

    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    safe_name = Path(pdf_file.filename).name
    upload_path = run_dir / "input" / safe_name
    _save_upload(pdf_file, upload_path)

    try:
        extracted_path = Path(extract_pdf(str(upload_path), output_dir=run_dir / "processed"))
        processed_path = run_dir / "processed" / f"{run_id}.json"
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted_path, processed_path)
        organized_path = Path(organize(processed_path, output_path=run_dir / "organized" / f"{run_id}_organized.json"))
        analysis_path = Path(
            analyze_organized_file(
                organized_path,
                output_path=run_dir / "analysis" / f"{run_id}_analysis.json",
                model=model.strip() or None,
                api_key=api_key.strip() or None,
            )
        )
        result = _load_analysis(analysis_path)
        result["run_dir"] = str(run_dir)
        result["processed_path"] = str(processed_path)
        result["organized_path"] = str(organized_path)
        result["analysis_path"] = str(analysis_path)
        return _render_page(result=result)
    except Exception as exc:  # pragma: no cover - surfaced in browser
        return _render_page(error=str(exc))


@app.get("/artifact/{run_id}/{artifact_type}")
def artifact(run_id: str, artifact_type: str):
    path_map = {
        "processed": RUNS_DIR / run_id / "processed" / f"{run_id}.json",
        "organized": RUNS_DIR / run_id / "organized" / f"{run_id}_organized.json",
        "analysis": RUNS_DIR / run_id / "analysis" / f"{run_id}_analysis.json",
    }
    path = path_map.get(artifact_type)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path, filename=path.name, media_type="application/json")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
