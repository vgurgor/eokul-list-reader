import json
from PyPDF2 import PdfReader
from datetime import datetime
import re
import logging
import os

# Loglama ayarları
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    
    # Zorunlu alanların kontrolü
    if not school_info["province"] or not school_info["district"] or not school_info["schoolName"]:
        logger.warning("Bazı okul bilgileri bulunamadı!")
        logger.debug(f"Mevcut okul bilgileri: {school_info}")
    
    return school_info

def extract_student_info(text_line):
    """Öğrenci bilgilerini satırdan ayıklar"""
    text_line = text_line.strip()
    if not text_line:
        return None
        
    logger.debug(f"Öğrenci satırı inceleniyor: {text_line}")
    
    # Örnek satır: " 101 HÜMEYRA Kız KARTAL  1"
    pattern = r'\s*(\d+)\s+([A-ZÇĞİÖŞÜÂ\s]+)\s+(Kız|Erkek)\s+([A-ZÇĞİÖŞÜÂ]+)\s+(\d+)'
    match = re.search(pattern, text_line)
    if match:
        student_id, name, gender, surname, order_no = match.groups()
        logger.debug(f"Öğrenci bilgisi bulundu: {order_no} - {name} {surname}")
        return {
            "orderNo": int(order_no),
            "studentId": student_id,
            "name": name.strip(),
            "surname": surname.strip(),
            "gender": "female" if gender == "Kız" else "male"
        }
    else:
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
        r'Anasınıfı\s*/\s*([A-Z])\s*Şubesi'
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
        elif "Anaokulu" in text:
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

def process_pdf(file_path):
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF dosyası bulunamadı: {file_path}")
            
        logger.info(f"PDF dosyası okunuyor: {file_path}")
        reader = PdfReader(file_path)
        
        if len(reader.pages) == 0:
            raise ValueError("PDF dosyası boş!")
            
        logger.info(f"PDF toplam sayfa sayısı: {len(reader.pages)}")
        
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
                text = page.extract_text()
                
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

def main():
    """Ana program fonksiyonu"""
    try:
        logger.info("Program başlatılıyor...")
        
        # Desteklenen PDF dosyaları
        pdf_files = ["example.pdf", "example2.pdf", "example3.pdf"]
        
        # İlk bulunan PDF dosyasını kullan
        pdf_file = None
        for file in pdf_files:
            if os.path.exists(file):
                pdf_file = file
                break
                
        if not pdf_file:
            raise FileNotFoundError(f"Hiçbir PDF dosyası bulunamadı ({', '.join(pdf_files)})")
            
        # PDF'i işle
        result = process_pdf(pdf_file)
        
        # Sonuçları JSON olarak kaydet
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        logger.info("İşlem tamamlandı. Sonuçlar output.json dosyasına kaydedildi.")
        logger.info(f"Toplam {len(result['classes'])} sınıf ve {sum(len(c['students']) for c in result['classes'])} öğrenci işlendi.")
        
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {str(e)}")
        print(f"Hata oluştu: {str(e)}")

if __name__ == "__main__":
    main() 