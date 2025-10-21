import uvicorn
from src import create_app


if __name__ == "__main__":
    uvicorn.run("main:create_app", reload=True, factory=True)
