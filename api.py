from fastapi import FastAPI, HTTPException
import aiohttp
import tempfile
import os
from pdf_reader import process_pdf
import logging
from pydantic import BaseModel
from typing import Optional

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="E-Okul PDF Okuyucu API",
    description="E-Okul'dan alınan PDF formatındaki öğrenci listelerini JSON formatına dönüştürür",
    version="1.0.0"
)

class PDFRequest(BaseModel):
    pdf_url: str

class APIResponse(BaseModel):
    status: bool
    message: str
    data: Optional[dict] = None

@app.post("/process-pdf", response_model=APIResponse)
async def process_pdf_url(request: PDFRequest):
    """PDF URL'sini alıp işleyen endpoint"""
    try:
        logger.info(f"PDF URL'si alındı: {request.pdf_url}")
        
        # PDF dosyasını geçici olarak indir
        async with aiohttp.ClientSession() as session:
            async with session.get(request.pdf_url) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="PDF dosyası indirilemedi")
                
                # Geçici dosya oluştur
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(await response.read())
                    temp_path = temp_file.name
        
        logger.info(f"PDF başarıyla indirildi: {temp_path}")
        
        try:
            # PDF'i işle
            result = process_pdf(temp_path, request.pdf_url)
            
            # Geçici dosyayı sil
            os.unlink(temp_path)
            
            if not result["success"]:
                # Başarısızlıkta da tanılama verilerini döndür
                return APIResponse(
                    status=False,
                    message=result.get("message", "İşleme hatası"),
                    data=result.get("data", {})
                )
            
            return APIResponse(
                status=True,
                message="PDF başarıyla işlendi",
                data=result["data"]
            )
            
        except Exception as e:
            # Hata durumunda geçici dosyayı silmeyi dene
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
            
    except Exception as e:
        logger.error(f"PDF işlenirken hata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Ana sayfa"""
    return {"message": "E-Okul PDF Okuyucu API'sine Hoş Geldiniz"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 