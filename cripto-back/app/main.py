from fastapi import FastAPI

app = FastAPI()

from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(docs_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url, # type: ignore
        title=app.title + " - Swagger UI",
        swagger_css_url="/static/swagger-ui-dark.css"
    )



@app.get("/")
async def greetings():
    return {"Hello": "world"}