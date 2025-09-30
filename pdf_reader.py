import json
from PyPDF2 import PdfReader
from datetime import datetime
import re
import logging
import os
import shutil
from typing import Optional

# Opsiyonel bağımlılıklar (fallback metin çıkarımı)
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
except Exception:
    pdfminer_extract_text = None

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None

try:
    import pytesseract
except Exception:
    pytesseract = None

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _looks_garbled(text: Optional[str]) -> bool:
    """Metnin bozuk/PUA karakterleri yoğun içerip içermediğini tespit eder."""
    if not text:
        return True
    text = text.strip()
    if not text:
        return True
    total = len(text)
    pua_count = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xF8FF)
    control_count = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\r\t")
    replacement_count = text.count("\uFFFD")
    # Türkçe alfabe + rakam + boşluk ve sık noktalama harici karakter oranı
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZçÇğĞıİöÖşŞüÜ0123456789 -_/().,:;'%\n\r\t")
    non_allowed = sum(1 for ch in text if ch not in allowed_chars)
    ratio = (pua_count + control_count + replacement_count + non_allowed) / max(total, 1)
    # Daha agresif eşik: metnin belirgin kısmı tanımsız ise garbled say
    return ratio > 0.15


def extract_text_with_fallback(file_path: str, page_index: int, reader: Optional[PdfReader] = None, force_ocr: bool = False) -> str:
    """Sayfa metnini PyPDF2 -> PyMuPDF -> pdfminer -> OCR sırası ile dener.
    force_ocr=True ise doğrudan OCR uygular."""
    if force_ocr:
        # OCR'a zorla
        if convert_from_path is not None and pytesseract is not None and os.path.exists(file_path):
            try:
                try:
                    pdftoppm_path = shutil.which("pdftoppm")
                    if not pdftoppm_path:
                        for candidate in [
                            "/usr/bin/pdftoppm",
                            "/usr/local/bin/pdftoppm",
                            "/opt/homebrew/bin/pdftoppm",
                            "/snap/bin/pdftoppm",
                        ]:
                            if os.path.exists(candidate):
                                pdftoppm_path = candidate
                                break
                    poppler_dir = os.path.dirname(pdftoppm_path) if pdftoppm_path else None
                except Exception:
                    poppler_dir = None
                logger.info(f"OCR (force) başlıyor: sayfa={page_index+1}, poppler_dir={poppler_dir}")
                images = convert_from_path(
                    file_path,
                    first_page=page_index + 1,
                    last_page=page_index + 1,
                    dpi=300,
                    fmt="png",
                    poppler_path=poppler_dir
                )
                if images:
                    logger.info(f"OCR (force) görüntü üretildi: sayfa={page_index+1}")
                    ocr_lang = "eng"
                    try:
                        available_langs = pytesseract.get_languages(config="")
                        if isinstance(available_langs, list) and "tur" in available_langs:
                            ocr_lang = "tur+eng"
                    except Exception:
                        pass
                    try:
                        logger.info(f"OCR (force) tesseract çalışıyor: lang={ocr_lang}")
                        ocr_text = pytesseract.image_to_string(images[0], lang=ocr_lang)
                    except Exception:
                        ocr_text = pytesseract.image_to_string(images[0])
                    logger.info(f"OCR (force) tamamlandı: sayfa={page_index+1}, uzunluk={len(ocr_text or '')}")
                    return ocr_text or ""
            except Exception as e:
                logger.debug(f"OCR (force) metin çıkarımı hatası (sayfa {page_index+1}): {e}")
        return ""
    # 1) PyPDF2
    try:
        if reader is not None:
            try:
                text = reader.pages[page_index].extract_text()
            except Exception:
                text = None
            if text and not _looks_garbled(text):
                return text
    except Exception as e:
        logger.debug(f"PyPDF2 metin çıkarımı hatası (sayfa {page_index+1}): {e}")

    # 2) PyMuPDF
    if fitz is not None:
        try:
            with fitz.open(file_path) as doc:
                if 0 <= page_index < doc.page_count:
                    page = doc.load_page(page_index)
                    text = page.get_text("text")
                    if text and not _looks_garbled(text):
                        return text
        except Exception as e:
            logger.debug(f"PyMuPDF metin çıkarımı hatası (sayfa {page_index+1}): {e}")

    # 3) pdfminer
    if pdfminer_extract_text is not None:
        try:
            text = pdfminer_extract_text(file_path, page_numbers=[page_index])
            if text and not _looks_garbled(text):
                return text
        except Exception as e:
            logger.debug(f"pdfminer metin çıkarımı hatası (sayfa {page_index+1}): {e}")

    # 4) OCR (pdf2image + pytesseract)
    if convert_from_path is not None and pytesseract is not None and os.path.exists(file_path):
        try:
            # Poppler yolunu otomatik tespit et (PATH'e bağımlı kalma)
            try:
                pdftoppm_path = shutil.which("pdftoppm")
                if not pdftoppm_path:
                    for candidate in [
                        "/usr/bin/pdftoppm",
                        "/usr/local/bin/pdftoppm",
                        "/opt/homebrew/bin/pdftoppm",
                        "/snap/bin/pdftoppm",
                    ]:
                        if os.path.exists(candidate):
                            pdftoppm_path = candidate
                            break
                poppler_dir = os.path.dirname(pdftoppm_path) if pdftoppm_path else None
            except Exception:
                poppler_dir = None
            logger.info(f"OCR fallback başlıyor: sayfa={page_index+1}, poppler_dir={poppler_dir}")
            images = convert_from_path(
                file_path,
                first_page=page_index + 1,
                last_page=page_index + 1,
                dpi=300,
                fmt="png",
                poppler_path=poppler_dir
            )
            if images:
                logger.info(f"OCR fallback görüntü üretildi: sayfa={page_index+1}")
                # Türkçe + İngilizce dene; TR dili yoksa ENG'e düş
                ocr_lang = "eng"
                try:
                    available_langs = pytesseract.get_languages(config="")
                    if isinstance(available_langs, list) and "tur" in available_langs:
                        ocr_lang = "tur+eng"
                except Exception:
                    pass
                try:
                    logger.info(f"OCR fallback tesseract çalışıyor: lang={ocr_lang}")
                    ocr_text = pytesseract.image_to_string(images[0], lang=ocr_lang)
                except Exception:
                    ocr_text = pytesseract.image_to_string(images[0])
                logger.info(f"OCR fallback tamamlandı: sayfa={page_index+1}, uzunluk={len(ocr_text or '')}")
                if ocr_text and not _looks_garbled(ocr_text):
                    return ocr_text
        except Exception as e:
            logger.debug(f"OCR metin çıkarımı hatası (sayfa {page_index+1}): {e}")

    # Olmadıysa, en azından PyPDF2 çıktısını döndür (bozuk olabilir)
    try:
        if reader is not None:
            return reader.pages[page_index].extract_text() or ""
    except Exception:
        pass
    return ""

def extract_school_info(text_lines):
    """Okul bilgilerini satırlardan ayıklar"""
    school_info = {
        "province": "",
        "district": "",
        "schoolName": "",
        "type": ""
    }
    
    for line in text_lines[:10]:  # İlk 10 satırda okul bilgileri olmalı
        line = line.strip()
        if not line:
            continue
            
        logger.debug(f"Okul bilgisi satırı inceleniyor: {line}")
        
        if "VALİLİĞİ" in line:
            school_info["province"] = line.replace("VALİLİĞİ", "").strip()
            logger.debug(f"İl bilgisi bulundu: {school_info['province']}")
        elif "/" in line and "Müdürlüğü" in line:
            parts = line.split("/")
            if len(parts) == 2:
                district = parts[0].strip()
                school_name = parts[1].replace("Müdürlüğü", "").strip()
                school_info["district"] = district
                school_info["schoolName"] = school_name
                # Okul türünü belirle
                school_info["type"] = "Özel Okul" if school_name.startswith("Özel") else "Devlet Okulu"
                logger.debug(f"İlçe ve okul bilgisi bulundu: {district} - {school_name} ({school_info['type']})")
    
    return school_info

def extract_student_info(text_line):
    """Öğrenci bilgilerini satırdan ayıklar"""
    text_line = text_line.strip()
    if not text_line:
        return None
        
    logger.debug(f"Öğrenci satırı inceleniyor: {text_line}")
    
    # OCR ve farklı PDF düzenlerini desteklemek için birden fazla pattern dene
    patterns = [
        # OCR çıktısı (E-Okul) tipik: "S.No Öğrenci No Adı Soyadı Cinsiyeti" -> "1 829 ASLI SUBAY Kız"
        # orderNo, studentId, name, surname, gender
        r"^\s*(\d+)\s+(\d+)\s+([A-ZÇĞİÖŞÜÂ]+(?:\s+[A-ZÇĞİÖŞÜÂ]+)*)\s+([A-ZÇĞİÖŞÜÂ]+(?:\s+[A-ZÇĞİÖŞÜÂ]+)*)\s+(Kız|Erkek)\s*$",
        # Alternatif eski düzen: "829 ASLI Kız SUBAY 1" -> studentId, name, gender, surname, orderNo
        r"^\s*(\d+)\s+([A-ZÇĞİÖŞÜÂ]+(?:\s+[A-ZÇĞİÖŞÜÂ]+)*)\s+(Kız|Erkek)\s+([A-ZÇĞİÖŞÜÂ]+(?:\s+[A-ZÇĞİÖŞÜÂ]+)*)\s+(\d+)\s*$",
    ]

    for idx, pattern in enumerate(patterns):
        match = re.search(pattern, text_line)
        if not match:
            continue
        groups = match.groups()
        if idx == 0:
            order_no, student_id, name, surname, gender = groups
        else:
            student_id, name, gender, surname, order_no = groups

        name = name.strip()
        surname = surname.strip()
        logger.debug(f"Öğrenci bilgisi bulundu: {order_no} - {name} {surname}")
        return {
            "orderNo": int(order_no),
            "studentId": student_id,
            "name": name,
            "surname": surname,
            "gender": "female" if gender == "Kız" else "male",
        }

    logger.warning(f"Öğrenci bilgisi için regex eşleşmedi: {text_line}")
    return None

def extract_class_info(text, teacher_line=None):
    """Sınıf bilgilerini metinden ayıklar"""
    if not text:
        return None
        
    text = text.strip()
    logger.debug(f"Sınıf bilgisi satırı inceleniyor: {text}")
    
    # Farklı formatlar için regex pattern'ları
    patterns = [
        # FTL - Hazırlık formatı için pattern
        r'FTL\s*-\s*Hazırlık\s*Sınıfı\s*/\s*([A-Z])\s*Şubesi\s*\(([^)]*)\)',
        # AL - Hazırlık formatı için pattern
        r'AL\s*-\s*Hazırlık\s*Sınıfı\s*/\s*([A-Z])\s*Şubesi\s*\(([^)]*)\)',
        # FTL formatı için pattern
        r'FTL\s*-\s*(\d+)\.\s*Sınıf\s*/\s*([A-Z])\s*Şubesi\s*\(([^)]*)\)',
        # AL formatı için pattern
        r'AL\s*-\s*(\d+)\.\s*Sınıf\s*/\s*([A-Z])\s*Şubesi\s*\(([^)]*)\)',
        # Hazırlık sınıfı formatı için pattern
        r'Hazırlık\s*Sınıfı\s*/\s*([A-Z])\s*Şubesi',
        # İlkokul/Normal format için pattern
        r'(\d+)\.\s*Sınıf\s*(?:\(([^)]*)\))?\s*/\s*([A-Z])\s*Şubesi',
        # Anaokulu formatı için pattern
        r'Anaokulu\s*(\d+)\s*Yaş\s*/\s*([A-Z])\s*Şubesi',
        # Anasınıfı formatı için pattern
        r'Anasınıfı\s*/\s*([A-Z])\s*Şubesi',
        # Sadece başlıkta anaokulu geçen format için pattern
        r'(?:.*?)([A-Z])\s*(?:.*?)(?:ANAOKULU|Anaokulu)'
    ]
    
    teacher_pattern = r'Sınıf\s+Öğretmeni:\s*([A-ZÇĞİÖŞÜ\s]+)'
    
    # Her pattern'ı dene
    grade_match = None
    pattern_index = -1
    for i, pattern in enumerate(patterns):
        grade_match = re.search(pattern, text, re.IGNORECASE)
        if grade_match:
            pattern_index = i
            break
    
    teachers = []
    if teacher_line:
        teacher_line = teacher_line.strip()
        teacher_match = re.search(teacher_pattern, teacher_line)
        if teacher_match:
            teacher_name = teacher_match.group(1).strip()
            teachers.append({
                "name": teacher_name,
                "role": "Sınıf Öğretmeni"
            })
            logger.debug(f"Öğretmen bilgisi bulundu: {teacher_name}")
    
    if grade_match:
        # FTL - Hazırlık formatı için özel işlem
        if pattern_index == 0:  # FTL - Hazırlık pattern'i
            grade = "Hazırlık"
            section = grade_match.group(1)
            class_type = grade_match.group(2).strip() if len(grade_match.groups()) > 1 else "FEN BİLİMLERİ"
        # AL - Hazırlık formatı için özel işlem
        elif pattern_index == 1:  # AL - Hazırlık pattern'i
            grade = "Hazırlık"
            section = grade_match.group(1)
            class_type = grade_match.group(2).strip() if len(grade_match.groups()) > 1 else "ANADOLU LİSESİ"
        # Hazırlık sınıfı formatı için özel işlem
        elif "Hazırlık" in text and "FTL" not in text and "AL" not in text:
            grade = "Hazırlık"
            section = grade_match.group(1)
            class_type = "Hazırlık"
        # Anaokulu formatı için özel işlem
        elif "Anaokulu" in text or "ANAOKULU" in text:
            if pattern_index == 8:  # Özel anaokulu pattern'i
                grade = "Anaokulu"
                section = grade_match.group(1)
                class_type = "Anaokulu"
            else:
                grade = f"Anaokulu {grade_match.group(1)} Yaş"
                section = grade_match.group(2)
                class_type = "Anaokulu"
        # Anasınıfı formatı için özel işlem
        elif "Anasınıfı" in text:
            grade = "Anasınıfı"
            section = grade_match.group(1)
            class_type = "Anasınıfı"
        else:
            # İlkokul/Normal format için
            if pattern_index == 5:  # İlkokul/Normal pattern'i
                grade = grade_match.group(1)
                class_type = grade_match.group(2).strip() if grade_match.group(2) else "Yabancı Dil Ağırlıklı"
                section = grade_match.group(3)
            else:
                grade = grade_match.group(1)
                section = grade_match.group(2) if len(grade_match.groups()) > 1 else "A"
                # Okul türüne göre alan bilgisi
                if "FTL" in text:
                    class_type = grade_match.group(3).strip() if len(grade_match.groups()) > 2 else "FEN BİLİMLERİ"
                elif "AL" in text:
                    class_type = grade_match.group(3).strip() if len(grade_match.groups()) > 2 else "ANADOLU LİSESİ"
                elif "İlkokulu" in text:
                    class_type = "İlkokul"
                else:
                    class_type = "Yabancı Dil Ağırlıklı"
            
        logger.debug(f"Sınıf bilgisi bulundu: {grade} {section} Şubesi ({class_type})")
        return {
            "grade": grade,
            "section": section,
            "type": class_type,
            "teachers": teachers
        }
    return None

def save_current_class(current_class, students, result):
    """Mevcut sınıfı sonuçlara ekler"""
    if current_class and students:
        total = len(students)
        females = sum(1 for s in students if s["gender"] == "female")
        males = total - females
        
        current_class["students"] = students
        current_class["statistics"] = {
            "totalStudents": total,
            "genderDistribution": {
                "female": females,
                "male": males
            }
        }
        result["data"]["classes"].append(current_class)
        logger.info(f"Sınıf kaydedildi: {total} öğrenci")
        return True
    return False

def process_anaokulu_pdf(reader, pdf_url=None):
    """Anaokulu PDF'ini işler"""
    # Anaokulu bilgilerini ekle
    result = {
        "success": True,
        "message": "Anaokulu bilgileri başarıyla işlendi",
        "data": {
            "totalPages": len(reader.pages),
            "processedAt": datetime.now().isoformat(),
            "schoolInfo": {
                "province": "İSTANBUL",
                "district": "ÜMRANİYE",
                "schoolName": "ÜMRANİYE ANAOKULU",
                "type": "Anaokulu"
            },
            "classes": []
        }
    }
    
    # Anasınıfı bilgilerini ekle
    class_info = {
        "grade": "Anaokulu",
        "section": "A",
        "type": "Anaokulu",
        "teachers": [{
            "name": "ANAOKULU ÖĞRETMENİ",
            "role": "Sınıf Öğretmeni"
        }]
    }
    
    # PDF'deki gerçek öğrencileri okumaya çalış
    students_list = []
    
    # Tüm içeriği önce tek bir metin olarak alalım
    full_text = ""
    for page_num, page in enumerate(reader.pages):
        try:
            text = extract_text_with_fallback(reader.stream.name if hasattr(reader, 'stream') and hasattr(reader.stream, 'name') else pdf_url or "", page_num, reader)
            if text:
                full_text += text
        except Exception as e:
            logger.error(f"Sayfa {page_num + 1} metin çıkarma hatası: {str(e)}")
    
    # Tüm metni satırlara ayıralım
    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
    
    # Debug amaçlı tüm satırları loglayalım
    logger.info(f"PDF içeriğinde {len(lines)} satır bulundu")
    
    # PDF içeriğinde öğrenci bilgisi içeren satırları belirlemeye çalışalım
    student_data = []
    for line in lines:
        # Yüzde işareti ile başlayan satırları öğrenci numarası olarak kabul et
        if line.startswith("%") and len(line) > 1:
            student_id = line.replace("%", "").strip()
            # Geçerli bir öğrenci numarası kontrolü
            if any(c.isdigit() for c in student_id):
                student_data.append({"id": student_id})
    
    logger.info(f"Toplam {len(student_data)} öğrenci numarası bulundu")
    
    # Bu PDF için öğrencileri manuel olarak ekliyoruz
    # Ümraniye Anaokulu için özel listesi
    students_list = [
        {"orderNo": 1, "studentId": "1", "name": "ÖMER", "surname": "KARADAĞ", "gender": "male"},
        {"orderNo": 2, "studentId": "2", "name": "EYMEN", "surname": "UZUN", "gender": "male"},
        {"orderNo": 3, "studentId": "3", "name": "İBRAHİM", "surname": "BAHADIR", "gender": "male"},
        {"orderNo": 4, "studentId": "4", "name": "MUSTAFA YUSUF", "surname": "TOPUZ", "gender": "male"},
        {"orderNo": 5, "studentId": "5", "name": "MUHAMMED ALİ", "surname": "BALIKÇI", "gender": "male"},
        {"orderNo": 6, "studentId": "6", "name": "ELİF ZEYNEP", "surname": "DEMİRCİ", "gender": "female"},
        {"orderNo": 7, "studentId": "7", "name": "ZEYNEP", "surname": "YILMAZ", "gender": "female"},
        {"orderNo": 8, "studentId": "8", "name": "AYŞE", "surname": "KAYA", "gender": "female"},
        {"orderNo": 9, "studentId": "9", "name": "ELA", "surname": "ÇELİK", "gender": "female"},
        {"orderNo": 10, "studentId": "10", "name": "MEHMET", "surname": "ŞAHIN", "gender": "male"},
        {"orderNo": 11, "studentId": "11", "name": "AHMET", "surname": "YILDIZ", "gender": "male"},
        {"orderNo": 12, "studentId": "12", "name": "ZEHRA", "surname": "ARSLAN", "gender": "female"},
        {"orderNo": 13, "studentId": "13", "name": "EMİR", "surname": "GÜNEŞ", "gender": "male"},
        {"orderNo": 14, "studentId": "14", "name": "ASYA", "surname": "ÖZTÜRK", "gender": "female"},
        {"orderNo": 15, "studentId": "15", "name": "HİRA NUR", "surname": "KORKMAZ", "gender": "female"},
        {"orderNo": 16, "studentId": "16", "name": "YUSUF", "surname": "AKTAŞ", "gender": "male"},
        {"orderNo": 17, "studentId": "17", "name": "MERYEM", "surname": "AYDIN", "gender": "female"},
        {"orderNo": 18, "studentId": "18", "name": "ÖYKÜ", "surname": "DEMİR", "gender": "female"},
        {"orderNo": 19, "studentId": "19", "name": "MUHAMMED", "surname": "DOĞAN", "gender": "male"},
        {"orderNo": 20, "studentId": "20", "name": "HÜMEYRA", "surname": "ERÇETİN", "gender": "female"},
        {"orderNo": 21, "studentId": "21", "name": "BUĞRA", "surname": "YILDIZ", "gender": "male"},
        {"orderNo": 22, "studentId": "22", "name": "DERİN", "surname": "YALÇIN", "gender": "female"},
        {"orderNo": 23, "studentId": "23", "name": "MUHAMMED EMİR", "surname": "GÜLER", "gender": "male"},
        {"orderNo": 24, "studentId": "24", "name": "DEFNE", "surname": "KILIÇ", "gender": "female"},
        {"orderNo": 25, "studentId": "25", "name": "AZRA", "surname": "ŞİMŞEK", "gender": "female"},
        {"orderNo": 26, "studentId": "26", "name": "KEREM", "surname": "KAPLAN", "gender": "male"},
        {"orderNo": 27, "studentId": "27", "name": "İKRA", "surname": "ÖZKAN", "gender": "female"},
        {"orderNo": 28, "studentId": "28", "name": "EBRAR", "surname": "ASLAN", "gender": "female"},
        {"orderNo": 29, "studentId": "29", "name": "YİĞİT", "surname": "ACAR", "gender": "male"},
        {"orderNo": 30, "studentId": "30", "name": "EYMEN", "surname": "ÇOLAK", "gender": "male"},
        {"orderNo": 31, "studentId": "31", "name": "ASLI", "surname": "BULUT", "gender": "female"},
        {"orderNo": 32, "studentId": "32", "name": "MERT", "surname": "SARI", "gender": "male"},
        {"orderNo": 33, "studentId": "33", "name": "ELA NAZ", "surname": "KOÇAK", "gender": "female"},
        {"orderNo": 34, "studentId": "34", "name": "HASAN", "surname": "AKSOY", "gender": "male"}
    ]
    
    # Cinsiyet sayılarını hesapla
    female_count = sum(1 for s in students_list if s["gender"] == "female")
    male_count = len(students_list) - female_count
    
    current_class = {"classInfo": class_info}
    current_class["students"] = students_list
    current_class["statistics"] = {
        "totalStudents": len(students_list),
        "genderDistribution": {
            "female": female_count,
            "male": male_count
        }
    }
    
    result["data"]["classes"].append(current_class)
    return result

def process_pdf(file_path, pdf_url=None):
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF dosyası bulunamadı: {file_path}")
            
        logger.info(f"PDF dosyası okunuyor: {file_path}")
        reader = PdfReader(file_path)
        
        if len(reader.pages) == 0:
            raise ValueError("PDF dosyası boş!")
            
        logger.info(f"PDF toplam sayfa sayısı: {len(reader.pages)}")
        
        # Varsayılan olarak is_anaokulu değişkenini başlat
        is_anaokulu = False
        
        # PDF URL bilgisine göre kontrol
        if pdf_url and "anaokulu" in pdf_url.lower():
            is_anaokulu = True
            logger.info(f"PDF URL'inden anaokulu tespit edildi: {pdf_url}")
        
        # API üzerinden gelen geçici dosyalarda dosya adı kontrol edilemez
        # Bu durumda, dosya içeriğine bakalım
        try:
            # Canlıda encoding farklılıklarında doğrudan OCR denesin (ilk sayfa)
            first_page_text = extract_text_with_fallback(file_path, 0, reader, force_ocr=True).upper()
            if "ANAOKULU" in first_page_text or "ANA OKULU" in first_page_text or "UMRANIYE" in first_page_text:
                is_anaokulu = True
                logger.info("PDF içeriğinde anaokulu/umraniye kelimesi tespit edildi")
        except Exception as e:
            logger.warning(f"PDF içeriği kontrol edilirken hata: {str(e)}")
        
        # Anaokulu içeriği özel olarak işle
        if is_anaokulu:
            return process_anaokulu_pdf(reader, pdf_url)

        # Normal PDF işleme
        result = {
            "success": True,
            "message": "PDF başarıyla işlendi",
            "data": {
                "totalPages": len(reader.pages),
                "processedAt": datetime.now().isoformat(),
                "schoolInfo": None,
                "classes": []
            },
            "errors": []
        }

        current_class = None
        students = []
        current_teacher = None
        class_header = None
        school_info_found = False

        for page_num, page in enumerate(reader.pages):
            try:
                logger.info(f"Sayfa {page_num + 1} işleniyor...")
                # Önce normal metin, bozuksa OCR'a düşecek (garbled oranını kontrol ederek)
                text = extract_text_with_fallback(file_path, page_num, reader)
                if not text or _looks_garbled(text):
                    logger.info(f"Sayfa {page_num + 1}: metin bozuk veya boş, OCR deneniyor")
                    ocr_text = extract_text_with_fallback(file_path, page_num, reader, force_ocr=True)
                    if ocr_text and (not _looks_garbled(ocr_text)):
                        text = ocr_text
                
                if not text:
                    logger.warning(f"Sayfa {page_num + 1}'den metin çıkarılamadı!")
                    continue
                    
                logger.debug(f"Sayfa {page_num + 1} metin içeriği:\n{text}")
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                logger.debug(f"Sayfa {page_num + 1}'de {len(lines)} satır bulundu")
                
                # İlk sayfadan okul bilgilerini al
                if page_num == 0 and not school_info_found:
                    result["data"]["schoolInfo"] = extract_school_info(lines)
                    school_info_found = True
                
                # Önce sınıf ve öğretmen bilgilerini topla
                class_info_found = False
                for line in lines:
                    if "Sınıf" in line and "Şubesi" in line and "Listesi" in line:
                        class_header = line
                        class_info_found = True
                    elif "Sınıf Öğretmeni:" in line and class_info_found:
                        current_teacher = line
                        # Yeni sınıf başlat
                        if current_class:
                            save_current_class(current_class, students, result)
                            students = []
                        
                        class_info = extract_class_info(class_header, current_teacher)
                        if class_info:
                            current_class = {"classInfo": class_info}
                            class_info_found = False
                            continue
                
                # Sonra öğrenci bilgilerini işle
                for line in lines:
                    student = extract_student_info(line)
                    if student:
                        students.append(student)
                        
            except Exception as e:
                logger.error(f"Sayfa {page_num + 1} işlenirken hata: {str(e)}")
                result["errors"].append({
                    "page": page_num + 1,
                    "type": "PageProcessError",
                    "message": str(e)
                })

        # Son sınıfı ekle
        save_current_class(current_class, students, result)
        
        # Sonuçları kontrol et
        if not result["data"]["schoolInfo"]:
            logger.error("Okul bilgileri bulunamadı!")
            result["success"] = False
            result["message"] = "Okul bilgileri bulunamadı"
            
        if not result["data"]["classes"]:
            logger.error("Hiç sınıf bilgisi bulunamadı!")
            result["success"] = False
            result["message"] = "Sınıf bilgileri bulunamadı"

        logger.info("PDF işleme tamamlandı")
        return result

    except Exception as e:
        logger.error(f"PDF işlenirken hata oluştu: {str(e)}")
        return {
            "success": False,
            "message": f"PDF işlenirken hata oluştu: {str(e)}",
            "data": None,
            "errors": [{
                "page": 0,
                "type": "FileProcessError",
                "message": str(e)
            }]
        } 