from flask import Flask, jsonify
import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [1] 커스텀 SSL 어댑터 (기존 유지) ---
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_context=ctx
        )

# --- [2] 파싱 함수 (기존 유지, 리스트 반환) ---
def parse_menu(html_code):
    soup = BeautifulSoup(html_code, 'html.parser')
    menu_items = soup.find_all("li", class_="more")
    results = []

    for item in menu_items:
        data = {}
        
        # 시간
        time_input = item.select_one("input[id^='sc']")
        data['time'] = time_input['value'] if time_input else "알수없음"

        # 구분
        label_div = item.find("div", class_="label")
        data['category'] = label_div.get_text(strip=True) if label_div else ""

        # 메뉴명, 가격
        tit_h4 = item.find("h4", class_="tit")
        if tit_h4:
            name_span = tit_h4.find("span", class_="tit")
            data['menu_name'] = name_span.get_text(strip=True) if name_span else ""
            price_span = tit_h4.find("span", class_="price")
            data['price'] = price_span.get_text(strip=True) if price_span else ""
        
        # 상세 내용
        dtl_p = item.find("p", class_="dtl")
        if dtl_p:
            cal_span = dtl_p.find("span", class_="cal")
            calories = cal_span.get_text(strip=True) if cal_span else ""
            data['calories'] = calories
            
            full_text = dtl_p.get_text(separator="\n", strip=True)
            # 상세내용 정제 (줄바꿈을 쉼표로, 칼로리 텍스트 제거)
            clean_detail = full_text.replace(calories, "").strip().replace('\n', ', ').replace(' · ', '')
            data['detail'] = clean_detail
            
        results.append(data)
    return results

# --- [3] 메인 라우트 (접속 시 실행되는 곳) ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def home(path):
    # 1. 날짜 계산 (KST = UTC+9)
    utc_now = datetime.now(timezone.utc)
    kst_timezone = timezone(timedelta(hours=9))
    kst_now = utc_now.astimezone(kst_timezone)
    
    yyyy = kst_now.strftime("%Y")
    mm = kst_now.strftime("%m")
    dd = kst_now.strftime("%d")
    
    # 2. URL 생성
    target_url = f"https://m.poswel.co.kr/fmenu//index.php?s_area=C&s_uid=13&section=%EC%A0%90%EC%8B%AC&s_date_y={yyyy}&s_date_m={mm}&s_date_d={dd}"

    # 3. 크롤링 준비
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    }
    
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())

    try:
        # Vercel 타임아웃(10초)을 고려하여 9초로 설정
        response = session.get(target_url, headers=headers, timeout=9)
        
        if response.status_code == 200:
            response.encoding = 'utf-8'
            menu_list = parse_menu(response.text)
            
            # 최종 결과 반환 (JSON)
            return jsonify({
                "status": "success",
                "date": f"{yyyy}-{mm}-{dd}",
                "count": len(menu_list),
                "data": menu_list
            })
        else:
            return jsonify({
                "status": "fail",
                "code": response.status_code,
                "message": "서버 접속 실패"
            }), 502

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# 로컬 테스트용
if __name__ == '__main__':
    app.run(debug=True)
