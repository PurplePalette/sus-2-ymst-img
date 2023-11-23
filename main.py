import os
import subprocess
import tempfile

import sus2ymst
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


def notation_text_to_svg(notation_text: str) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        text_file_path = os.path.join(temp_dir, "notation.txt")
        with open(text_file_path, "w") as f:
            f.write(notation_text)

        ret = subprocess.run(["php", "svg.php", temp_dir])
        if ret.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to convert")

        svg_file_path = os.path.join(temp_dir, "notation.svg")
        with open(svg_file_path, "r", encoding="utf-8") as f:
            svg_text = f.read()
    return svg_text


@app.post("/convert")
async def convert(
    request: Request,
    chart: str = Form(),
    textFlag: bool = Form(),
    laneFlag: bool = Form(),
):
    # テキストファイルの場合は、変換しない
    if textFlag:
        svg_text = notation_text_to_svg(chart)
        return templates.TemplateResponse(
            "convert.html", {"request": request, "svg_text": svg_text}
        )
    else:
        lane_offset = 0 if laneFlag else 2
        try:
            notation_txt, error_messages = sus2ymst.loads(chart, lane_offset)
            svg_text = notation_text_to_svg(notation_txt)
        except Exception:
            raise HTTPException(status_code=500)
        return templates.TemplateResponse(
            "convert.html",
            {
                "request": request,
                "svg_text": svg_text,
                "error_messages": error_messages,
            },
        )


@app.get("/")
async def index(request: Request):
    client_host = request.client.host
    return templates.TemplateResponse(
        "index.html", {"request": request, "host": client_host}
    )


if __name__ == "__main__":
    uvicorn.run("main:app", port=8080, reload=True)
