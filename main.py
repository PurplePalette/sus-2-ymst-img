import os
import subprocess
import tempfile

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import FileResponse

from process.notation import Sus2Ymst

app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/convert")
async def convert(request: Request, chart: str = Form(), textFlag: bool = Form()):
    # 一時ディレクトリの作成
    with tempfile.TemporaryDirectory() as temp_dir:
        if textFlag:
            notation_txt = chart
        else:
            # アップロードされたファイルを一時ディレクトリに保存
            file_path = os.path.join(temp_dir, "notation.sus")
            with open(file_path, "w") as f:
                f.write(chart)
            sus2ymst = Sus2Ymst(file_path)
            try:
                notation_txt = sus2ymst.convert()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        text_file_path = os.path.join(temp_dir, "notation.txt")
        with open(text_file_path, "w") as f:
            f.write(notation_txt)

        ret = subprocess.run(["php", "svg.php", temp_dir])
        if ret.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to convert")

        svg_file_path = os.path.join(temp_dir, "notation.svg")
        with open(svg_file_path, "r", encoding="utf-8") as f:
            svg_text = f.read()

        return templates.TemplateResponse(
            "convert.html", {"request": request, "svg_text": svg_text}
        )


@app.get("/")
async def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    uvicorn.run("main:app", port=8080, reload=True)
