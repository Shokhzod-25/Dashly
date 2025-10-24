import uvicorn
from src import create_app
import os
from dotenv import load_dotenv

load_dotenv()

PORT = os.getenv("PORT", 4444)
print(PORT)


if __name__ == "__main__":
    uvicorn.run("main:create_app", reload=True, host="0.0.0.0", port=int(PORT), factory=True)
