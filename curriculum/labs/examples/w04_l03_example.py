from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = FastAPI()

class Document(BaseModel):
    id: int
    title: str

def fetch_fixture():
    return {1: {'id': 1, 'title': 'sample', 'path': 'private'}}

@app.get('/documents/{key}', response_model=Document)
def read(key: int, rows: Annotated[dict, Depends(fetch_fixture)]):
    if key not in rows:
        raise HTTPException(404, 'document unavailable')
    return rows[key]

if __name__ == '__main__':
    with TestClient(app) as client:
        item = client.get('/documents/1')
        print(item.status_code, sorted(item.json()))
        print(client.get('/documents/999').status_code)
