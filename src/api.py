from fastapi import FastAPI
from .model import User

app = FastAPI()

@app.get("/users/{user_id}")
def get_user(user_id: int) -> User:
    raise NotImplementedError
