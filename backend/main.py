from fastapi import FastAPI, File, UploadFile
import pandas as pd
import io
from .stats import get_total_read

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello World"}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile):
    contents = await file.read()
    df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
    # contains 'read' books
    read_df = df[df['Exclusive Shelf'].str.lower() == 'read']
    total_read = get_total_read(read_df)
    
    print(read_df)
    
    return {
        "total_read": total_read
    }