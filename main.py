import uvicorn
from src import create_app


if __name__ == "__main__":
    uvicorn.run("main:create_app", reload=True, host="0.0.0.0", port=4000, factory=True)
