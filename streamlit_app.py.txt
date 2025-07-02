# streamlit_app.py

import streamlit as st
import pandas as pd
from datetime import datetime
from googleapiclient.discovery import build
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

# ▶️ API KEY 입력
API_KEY = st.secrets["api_key"]  # Streamlit Cloud에서는 secrets로 보관

# ▶️ 유튜브 API 연결
youtube = build('youtube', 'v3', developerKey=API_KEY)

# ▶️ 키워드 입력 UI
st.title("📺 YouTube 인플루언서 분석 툴")
keyword = st.text_input("🔍 분석할 키워드 입력 (예: ハンドメイド)", "ハンドメイド")

max_channels = st.slider("채널 수", min_value=10, max_value=50, value=30)

if st.button("🔎 분석 시작"):
    with st.spinner("유튜버 리스트 수집 중..."):

        # 1. 유튜브 검색 → 채널 ID 수집
        channel_ids = set()
        channel_titles = dict()

        search_response = youtube.search().list(
            q=keyword,
            part="snippet",
            type="video",
            maxResults=max_channels
        ).execute()

        for item in search_response['items']:
            channel_id = item['snippet']['channelId']
            channel_title = item['snippet']['channelTitle']
            channel_ids.add(channel_id)
            channel_titles[channel_id] = channel_title

        # 2. 채널 정보 수집
        channel_data = []

        for channel_id in channel_ids:
            try:
                info = youtube.channels().list(
                    part="snippet,statistics,contentDetails",
                    id=channel_id
                ).execute()

                item = info['items'][0]
                title = item['snippet']['title']
                published = item['snippet']['publishedAt']
                subscribers = int(item['statistics'].get('subscriberCount', 0))
                video_count = int(item['statistics'].get('videoCount', 0))
                uploads_playlist = item['contentDetails']['relatedPlaylists']['uploads']

                # 최근 영상 10개 수집
                video_ids, video_dates = [], []
                next_page_token = None

                while len(video_ids) < 10:
                    playlist_response = youtube.playlistItems().list(
                        part='snippet',
                        playlistId=uploads_playlist,
                        maxResults=50,
                        pageToken=next_page_token
                    ).execute()

                    for vid in playlist_response['items']:
                        video_ids.append(vid['snippet']['resourceId']['videoId'])
                        video_dates.append(vid['snippet']['publishedAt'])
                        if len(video_ids) >= 10:
                            break

                    next_page_token = playlist_response.get('nextPageToken')
                    if not next_page_token:
                        break

                # 영상 조회수 수집
                views = []
                if video_ids:
                    stats = youtube.videos().list(
                        part='statistics',
                        id=','.join(video_ids[:10])
                    ).execute()

                    for v in stats['items']:
                        views.append(int(v['statistics'].get('viewCount', 0)))

                avg_views = sum(views) // len(views) if views else 0
                latest_date = max(video_dates) if video_dates else None

                # 언어 판단
                is_ja = False
                sample_titles = " ".join([vid['snippet']['title'] for vid in playlist_response['items'][:5]])
                try:
                    lang = detect(sample_titles)
                    is_ja = lang == 'ja'
                except LangDetectException:
                    pass

                channel_data.append({
                    '채널명': title,
                    '채널 ID': channel_id,
                    '구독자 수': subscribers,
                    '영상 수': video_count,
                    '평균 조회수': avg_views,
                    '최근 영상 업로드일': latest_date,
                    '영상 휴면일수': (pd.Timestamp.today().tz_localize(None) - pd.to_datetime(latest_date).tz_localize(None)).days if latest_date else None,
                    '일본어 채널 여부': is_ja
                })

            except Exception as e:
                st.warning(f"채널 {channel_id} 오류: {e}")
                continue

    df = pd.DataFrame(channel_data)

    # 쉼표 표시용 컬럼
    df['구독자 수 (표시용)'] = df['구독자 수'].apply(lambda x: f"{x:,}")
    df['평균 조회수 (표시용)'] = df['평균 조회수'].apply(lambda x: f"{x:,}")

    df = df[df['일본어 채널 여부'] == True]
    df = df.sort_values("평균 조회수", ascending=False)

    st.success(f"{len(df)}개의 일본어 채널 분석 완료!")
    st.dataframe(df[[
        '채널명', '구독자 수 (표시용)', '평균 조회수 (표시용)',
        '최근 영상 업로드일', '영상 휴면일수'
    ]].reset_index(drop=True))
