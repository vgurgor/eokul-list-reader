# 📚 E-Okul Öğrenci Listesi PDF Okuyucu API

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-green?logo=fastapi)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-production-green.svg)

</div>

Bu FastAPI servisi, E-Okul'dan alınan PDF formatındaki öğrenci listelerini JSON formatına dönüştürür.

## ✨ Özellikler

- 🔄 PDF URL'den otomatik indirme
- 📝 PDF dosyasından sınıf bilgilerini okur
- 👥 Öğrenci bilgilerini (no, öğrenci no, ad, soyad, cinsiyet) ayıklar
- 👨‍🏫 Sınıf öğretmeni bilgilerini işler
- 📊 Sınıf istatistiklerini hesaplar (toplam öğrenci, cinsiyet dağılımı)
- ⚠️ Hata yönetimi ve raporlama
- 🚀 FastAPI ile REST API desteği
- 🔄 Çoklu format desteği (FTL, AL, İlkokul, Anaokulu)
- ⚡ Yüksek performans için çoklu işçi (worker) desteği

## 📋 Desteklenen Formatlar

| Format | Örnek |
|--------|-------|
| 🏫 FTL | "FTL - 9. Sınıf / A Şubesi" |
| 🎓 AL | "AL - 12. Sınıf / C Şubesi" |
| 🏫 İlkokul | "4. Sınıf / D Şubesi" |
| 🎈 Anaokulu | "Anaokulu 4 Yaş / A Şubesi" |
| 🎈 Anasınıfı | "Anasınıfı / A Şubesi" |

## 🚀 Production Kurulum

### 🛠️ Sistem Gereksinimleri

| Gereksinim | Versiyon | Açıklama |
|------------|----------|-----------|
| 🐍 Python | 3.8+ | Temel programlama dili |
| 📦 pip | En son | Python paket yöneticisi |
| 🌐 Nginx | 1.18+ | Web sunucusu (önerilen) |

### 📥 Kurulum Adımları

1. **Sistem Paketlerini Yükle**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv nginx
```

2. **Proje Kurulumu**
```bash
# Proje dizinini oluştur
sudo mkdir /opt/eokul-pdf-reader
sudo chown www-data:www-data /opt/eokul-pdf-reader
cd /opt/eokul-pdf-reader

# Projeyi klonla ve kur
git clone https://github.com/your-username/eokul-pdf-reader.git .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 🔧 Servis Yapılandırması

1. **Systemd Servisi**
```ini
[Unit]
Description=E-Okul PDF Reader API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/eokul-pdf-reader
Environment="PATH=/opt/eokul-pdf-reader/venv/bin"
Environment="PYTHONPATH=/opt/eokul-pdf-reader"
ExecStart=/opt/eokul-pdf-reader/venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

2. **Nginx Yapılandırması**
```nginx
upstream eokul_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    client_max_body_size 10M;

    location / {
        proxy_pass http://eokul_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_connect_timeout 30s;
        proxy_send_timeout    200s;
        proxy_read_timeout    200s;
        send_timeout          200s;
    }
}
```

## 🔁 Sunucuda Güncelleme (Deploy/Update)

### 1) Sunucuya bağlan
```bash
ssh your-user@your-server
```

### 2) Proje dizinine geç ve son değişiklikleri çek
```bash
cd /opt/eokul-pdf-reader
sudo -u www-data git fetch --all --prune
sudo -u www-data git reset --hard origin/main
```

### 3) Sanal ortamı etkinleştir ve bağımlılıkları güncelle
```bash
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

OCR için sistem bağımlılıkları (gerekirse):
```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-tur poppler-utils
tesseract --list-langs | grep -E "tur|eng"
```

### 4) Servisi yeniden başlat
```bash
sudo systemctl restart eokul-pdf-reader
```

Unit dosyasında değişiklik yaptıysanız:
```bash
sudo systemctl daemon-reload
sudo systemctl restart eokul-pdf-reader
```

### 5) Durumu ve logları kontrol et
```bash
sudo systemctl status eokul-pdf-reader --no-pager
sudo journalctl -u eokul-pdf-reader -n 200 --no-pager
```

### 6) Hızlı sağlık kontrolü
```bash
curl -s http://127.0.0.1:8000/ | jq .
curl -s -X POST http://127.0.0.1:8000/process-pdf \
  -H 'Content-Type: application/json' \
  -d '{"pdf_url":"https://example.com/sample.pdf"}' | jq .
```

## 📝 Örnek Kullanım

### 🐍 Python
```python
import requests

url = "https://your-domain.com/process-pdf"
data = {
    "pdf_url": "https://example.com/student-list.pdf"
}

response = requests.post(url, json=data)
print(response.json())
```

### 🌐 JavaScript
```javascript
fetch('https://your-domain.com/process-pdf', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        pdf_url: 'https://example.com/student-list.pdf'
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

## 📚 Dokümantasyon

- 📖 [Swagger UI](https://your-domain.com/docs)
- 📑 [ReDoc](https://your-domain.com/redoc)

## 📞 Destek

Sorunlarınız için [GitHub Issues](https://github.com/your-username/eokul-pdf-reader/issues) sayfasını kullanabilirsiniz.

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakınız.