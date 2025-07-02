import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from langdetect import detect
from datetime import datetime
import time

# ✅ YouTube API 키
API_KEY = st.secrets["api_key"]

# ✅ YouTube API 클라이언트 생성
youtube = build("youtube", "v3", developerKey=API_KEY)

# ✅ 함수: 키워드로 관련 영상들에서 유니크한 유튜버 ID 추출
def get_channel_ids(keyword, total_channels=100):
    channel_ids = set()
    channel_titles = dict()
    next_page_token = None

    while len(channel_ids) < total_channels:
        response = youtube.search().list(
            q=keyword,
            part="snippet",
            type="video",
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in response['items']:
            cid = item['snippet']['channelId']
            title = item['snippet']['channelTitle']
            if cid not in channel_ids:
                channel_ids.add(cid)
                channel_titles[cid] = title
                if len(channel_ids) >= total_channels:
                    break

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return list(channel_ids), channel_titles

# ✅ 함수: 채널 상세 정보 가져오기
def get_channel_stats(channel_id):
    response = youtube.channels().list(
        part="snippet,statistics",
        id=channel_id
    ).execute()
    
    item = response['items'][0]
    stats = item['statistics']
    snippet = item['snippet']

    subscribers = stats.get('subscriberCount', 0)
    video_count = stats.get('videoCount', 0)
    published_at = snippet.get('publishedAt')

    return int(subscribers), int(video_count), published_at

# ✅ 함수: 채널 언어가 일본어인지 판별
def is_japanese_channel(channel_title):
    try:
        lang = detect(channel_title)
        return lang == 'ja'
    except:
        return False

# ✅ 함수: 평균 조회수와 최신 영상 날짜 추출
def get_avg_views_and_latest(channel_id, max_videos=10):
    uploads = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",
        maxResults=max_videos,
        type="video"
    ).execute()

    video_ids = [item['id']['videoId'] for item in uploads['items'] if 'videoId' in item['id']]
    if not video_ids:
        return 0, None

    stats = youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids)
    ).execute()

    views = []
    upload_dates = []

    for item in stats['items']:
        view_count = int(item['statistics'].get('viewCount', 0))
        upload_date = item['snippet'].get('publishedAt')
        views.append(view_count)
        upload_dates.append(upload_date)

    avg_views = sum(views) // len(views) if views else 0
    latest_date = max(upload_dates) if upload_dates else None
    return avg_views, latest_date

# ✅ Streamlit 인터페이스
st.title("🇯🇵 일본 유튜버 분석 도구")
keyword = st.text_input("🔍 분석할 키워드를 입력하세요", value="ハンドメイド")

if st.button("🔎 검색"):
    with st.spinner("유튜버 분석 중... 잠시만 기다려 주세요"):
        channel_ids, channel_titles = get_channel_ids(keyword, total_channels=100)

        data = []
        for cid in channel_ids:
            if not is_japanese_channel(channel_titles[cid]):
                continue

            try:
                subs, vids, created_at = get_channel_stats(cid)
                avg_views, latest_upload = get_avg_views_and_latest(cid)
                latest_upload_dt = pd.to_datetime(latest_upload).tz_localize(None) if latest_upload else None
                dormancy_days = (pd.Timestamp.now() - latest_upload_dt).days if latest_upload_dt else None

                data.append({
                    "채널명": channel_titles[cid],
                    "채널 ID": cid,
                    "채널 URL": f"https://www.youtube.com/channel/{cid}",
                    "구독자 수": subs,
                    "영상 수": vids,
                    "평균 조회수": avg_views,
                    "최근 영상 업로드일": latest_upload_dt.date() if latest_upload_dt else None,
                    "영상 휴면일수": dormancy_days
                })
            except Exception as e:
                print(f"오류 발생: {e}")
                continue
            time.sleep(0.3)

        df = pd.DataFrame(data)

        # 숫자 포맷 컬럼 추가
        df['구독자 수 (표시용)'] = df['구독자 수'].apply(lambda x: f"{x:,}")
        df['평균 조회수 (표시용)'] = df['평균 조회수'].apply(lambda x: f"{x:,}")

        # 보기 좋게 정렬
        df.sort_values(by="평균 조회수", ascending=False, inplace=True)

        # 표시용 컬럼만 선택
        display_df = df[[
            "채널명", "채널 URL", "구독자 수 (표시용)", "평균 조회수 (표시용)",
            "최근 영상 업로드일", "영상 휴면일수"
        ]]

        # 결과 출력
        st.success(f"🔍 총 {len(display_df)}명의 일본어 유튜버를 분석했습니다!")
        st.dataframe(display_df, use_container_width=True)
