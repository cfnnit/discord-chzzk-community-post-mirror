import time
import urllib.request
import json
import os
from datetime import datetime

# ================= Config =================
CHANNEL_ID = ""                                  # 채널 ID 
POLL_INTERVAL_SEC = 30                           # 갱신 주기. 입력된 값마다 새 포스트가 올라왔는지 확인함
SEEN_POSTS_FILE = "seen_posts.txt"               # 이미 수집한 게시글 ID 기록용 파일
OUTPUT_FILE = "collected_posts.jsonl"            # 수집한 포스트의 내용이 기록될 파일
DISCORD_WEBHOOK_URL = ""                         # 디스코드 웹훅 URL
# ==========================================

def load_seen_posts():
    if os.path.exists(SEEN_POSTS_FILE):
        with open(SEEN_POSTS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_post(post_id):
    with open(SEEN_POSTS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{post_id}\n")

def trim_output_file():
    if not os.path.exists(OUTPUT_FILE):
        return
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) >= 30:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines[-10:])
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 파일 정리 중 오류: {e}")

def send_discord_webhook(post_id, content, images):
    if not DISCORD_WEBHOOK_URL:
        return
        
    post_url = f"https://chzzk.naver.com/{CHANNEL_ID}/community/detail/{post_id}"
    safe_content = content if len(content) <= 4000 else content[:4000] + "..."

    # ================= Embeds =================
    data = {
        "embeds": [
            {
                "author": {
                    "name": "", #임베드에 뜰 이름. 보통 스머 이름으로 하면됨
                    "icon_url": "" #임베드에 뜰 프사. 알아서 하셈
                },
                "description": safe_content + f"\n\n[🔗 치지직 커뮤니티에서 보기]({post_url})",
                "color": 0x00FE3E,
                "url": post_url
            }
        ]
    }
    # ==========================================
  
    if images:
        data["embeds"][0]["image"] = {"url": images[0]}
        for img in images[1:10]:
            data["embeds"].append({
                "url": post_url,
                "image": {"url": img}
            })
            
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            pass
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 디스코드 웹훅 전송 실패: {e}", flush=True)

def fetch_latest_posts(channel_id):
    # 나쁜짓을 하자. 공식적으로 제공하는 기능이 아니기 때문에 이런 짓을 했읍니다.
    url = f"https://apis.naver.com/nng_main/nng_comment_api/v1/type/CHANNEL_POST/id/{channel_id}/comments?limit=10&offset=0&orderType=DESC&pagingType=PAGE"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://chzzk.naver.com",
        "Referer": f"https://chzzk.naver.com/{channel_id}/community",
        "front-client-platform-type": "PC",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("content", {}).get("comments", {}).get("data", [])
    except urllib.error.HTTPError as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTP 에러: {e.code}, 이유: {e.reason}")
        print(e.read().decode('utf-8'))
        return []
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API 호출 에러: {e}")
        return []

def collect_new_posts():
    seen_posts = load_seen_posts()
    posts = fetch_latest_posts(CHANNEL_ID)
    
    if not posts:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 수집할 게시글이 없습니다.", flush=True)
        return

    posts = list(reversed(posts))
    new_count = 0
    for item in posts:
        comment_info = item.get("comment", {})
        post_id = str(comment_info.get("commentId"))
        if not post_id or post_id in seen_posts:
            continue
        content = comment_info.get("content", "")
        created_date = comment_info.get("createdDate", "")
        images = []
        attaches = comment_info.get("attaches")
        if isinstance(attaches, list):
            for attach in attaches:
                if isinstance(attach, dict) and attach.get("attachType") == "PHOTO":
                    img_url = attach.get("attachValue")
                    if img_url:
                        images.append(img_url)
                        
        post_data = {
            "post_id": post_id,
            "collected_at": datetime.now().isoformat()
        }

        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            jsonString = json.dumps(post_data, ensure_ascii=False)
            f.write(jsonString + "\n")
            
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 새 글 수집 됨! ID: {post_id}", flush=True)
        print(f"내용: {content[:100]}...\n", flush=True)
        if images:
            print(f"포함된 이미지 개수: {len(images)}개", flush=True)
        
        send_discord_webhook(post_id, content, images)
        save_seen_post(post_id)
        seen_posts.add(post_id)

    trim_output_file()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 수집 완료. 현재까지 확인된 글 개수: {len(seen_posts)}", flush=True)

def main():
    print("=" * 50, flush=True)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 수집기 시작...", flush=True)
    print(f"> 대상 채널 ID: {CHANNEL_ID}", flush=True)
    print(f"> 수집 주기: {POLL_INTERVAL_SEC}초 ({(POLL_INTERVAL_SEC / 60):.1f} 분)", flush=True)
    print(f"> 데이터 저장 파일: {OUTPUT_FILE}", flush=True)
    print("=" * 50, flush=True)
    
    if not os.path.exists(SEEN_POSTS_FILE) or os.path.getsize(SEEN_POSTS_FILE) == 0:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 최초 실행 감지: 초기 데이터를 세팅합니다.", flush=True)
        initial_posts = fetch_latest_posts(CHANNEL_ID)
        for item in initial_posts:
            post_id = str(item.get("comment", {}).get("commentId", ""))
            if post_id:
                save_seen_post(post_id)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 초기 세팅 완료! 이후 올라오는 새 글부터 알림을 보냅니다.", flush=True)
    
    while True:
        try:
            collect_new_posts()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 메인 루프 에러: {e}", flush=True)
        time.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    main()
