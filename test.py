import logging
logging.basicConfig(level=logging.INFO)
from pdf_reader import process_pdf

# Belirtilen URL'deki PDF'yi işle
result = process_pdf('/tmp/test.pdf', 'https://content.stoys.co/mebpdf/kurum2/2025-3/1/umraniye_anaokulu_2025_3_1742812519.pdf')

if result and result['success']:
    print(f"Öğrenci Sayısı: {len(result['data']['classes'][0]['students'])}")
    print('İlk 3 öğrenci:')
    for i, student in enumerate(result['data']['classes'][0]['students'][:3]):
        print(f"{i+1}. {student['name']} {student['surname']} ({student['gender']})")
else:
    print("Hata oluştu:", result['message'] if result else "Sonuç alınamadı") 