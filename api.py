from fastapi import FastAPI, HTTPException
import aiohttp
import asyncio
import tempfile
import os
from pdf_reader import process_pdf
import logging
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PDF_DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=15)
PDF_PROCESS_TIMEOUT_SECONDS = 180

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
        
        async with aiohttp.ClientSession(timeout=PDF_DOWNLOAD_TIMEOUT) as session:
            async with session.get(request.pdf_url) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"PDF dosyası indirilemedi (HTTP {response.status})"
                    )
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(await response.read())
                    temp_path = temp_file.name
        
        logger.info(f"PDF başarıyla indirildi: {temp_path}")
        
        try:
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, process_pdf, temp_path, request.pdf_url),
                timeout=PDF_PROCESS_TIMEOUT_SECONDS,
            )
            
            os.unlink(temp_path)
            
            if not result["success"]:
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
            
        except asyncio.TimeoutError:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            logger.error(f"PDF işleme zaman aşımına uğradı ({PDF_PROCESS_TIMEOUT_SECONDS}s): {request.pdf_url}")
            raise HTTPException(
                status_code=504,
                detail=f"PDF işleme {PDF_PROCESS_TIMEOUT_SECONDS} saniye içinde tamamlanamadı"
            )
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
    
    except aiohttp.ClientError as e:
        logger.error(f"PDF indirme hatası: {str(e)}")
        raise HTTPException(status_code=502, detail=f"PDF indirilemedi: {str(e)}")
    except HTTPException:
        raise
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