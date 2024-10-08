from fastapi import FastAPI, UploadFile, File, HTTPException
import pytesseract
import cv2
import re
import numpy as np

from typing import Any, List, Union
from pydantic import BaseModel

app = FastAPI()
# uvicorn main:app --reload로 실행

# Tesseract 경로 설정 (Windows 환경일 경우 필요)
# 배포 환경은 linux기 때문에 미리 설치한 후 경로 변경하기 
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class Payment(BaseModel):
    order_amount: int
    delivery_tip: int
    discount: int

@app.post("/image", response_model=Payment, status_code=200)
async def read_item(file: UploadFile = File(...)):
    # 파일 내용을 바이트로 읽음
    file_bytes = await file.read()
    
    # 이미지 데이터를 numpy 배열로 변환
    image_np = np.frombuffer(file_bytes, np.uint8)
    
    # OpenCV로 이미지 디코딩 (메모리에서 읽기)
    img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

    # 이미지 전처리 (필요에 따라 대비 증가, 회색 변환)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 임계값 적용 (Thresholding) - 노이즈 제거 및 텍스트 뚜렷하게
    _, threshold_img = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    # OCR로 텍스트 추출
    text = pytesseract.image_to_string(threshold_img, lang='kor')  # 'kor'은 한글을 인식하기 위한 설정

    # 추출된 텍스트에서 불필요한 공백과 줄바꿈 제거
    cleaned_text = re.sub(r'\s+', '', text)
    
    # 결제 금액, 주문 금액, 배달팁, 할인 정보 추출
    total_amount_match = re.search(r'결제금액(\d{1,3}(?:,\d{3})*원)', cleaned_text)
    order_amount_match = re.search(r'주문금액(\d{1,3}(?:,\d{3})*원)', cleaned_text)
    delivery_tip_match = re.search(r'배달팁.*?(\d{1,3}(?:,\d{3})*원)', cleaned_text)
    discount_match = re.search(r'할인.*?(-\d{1,3}(?:,\d{3})*원)', cleaned_text)

    # 매칭 결과에서 금액을 추출(,랑 '원' 제거)하고 형변환
    try:
        total_amount = int(total_amount_match.group(1).replace('원', '').replace(',', '')) if total_amount_match else 0
        order_amount = int(order_amount_match.group(1).replace('원', '').replace(',', '')) if order_amount_match else 0
        delivery_tip = int(delivery_tip_match.group(1).replace('원', '').replace(',', '')) if delivery_tip_match else 0
        discount = int(discount_match.group(1).replace('원', '').replace(',', '')) if discount_match else 0

    except ValueError:
        raise HTTPException(status_code=400, detail="금액 형식이 잘못되었습니다.")

    
    if(order_amount + delivery_tip + discount != total_amount):
        raise HTTPException(status_code=400, detail="이미지가 잘못되었습니다. 다시 업로드해주세요.")
    
    # 결과 반환
    return Payment(order_amount=order_amount, delivery_tip=delivery_tip, discount=discount)

# 원까지 붙여서 그냥 반환하고 메인 서버에서 그냥 마지막 글자 '원'만 떼고 Integer.parseInt 해버리면 됨
# 아니면 여기에서 바로 배달팁 + 배민클럽할인금액 계산해서 반환하면 배달팁 계산 가능
# 주문금액 + 배달팁 + 배민클럽 할인 = 결제금액 -> 이렇게 계산해서 일치하면 pass 아니면 조작 판정
# 조작이 아니라면 그냥 저 세 값 주고 계산해버리면 됨
# 어차피 주문 금액 가져오는건 쿠폰쓰는거랑 연관 없음
# 쿠폰은 스팟 주최자의 음식값을 빼는거라 생각하면 됨