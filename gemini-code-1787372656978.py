import streamlit as st
import pandas as pd
import io
import math
import matplotlib.pyplot as plt
import re
import ezdxf
import pyproj
from geopy.geocoders import Nominatim
from shapely.geometry import LineString, Point

# --- 1. EPSG 좌표계 변환 설정 (Bessel 중부원점 5174 -> GPS 4326) ---
try:
    transformer = pyproj.Transformer.from_crs("epsg:5174", "epsg:4326", always_xy=True)
except Exception as e:
    st.error(f"좌표 변환기 설정 오류: {e}")

# --- 2. DXF에서 배관 데이터 추출 함수 ---
def extract_pipes(dxf_stream, layer_name=None):
    try:
        doc = ezdxf.read(dxf_stream)
        msp = doc.modelspace()
        pipes = []
        texts = []

        # 선(Line) 추출
        if layer_name:
            lines = msp.query(f'LINE[layer=="{layer_name}"]')
            text_query = f'TEXT MTEXT[layer=="{layer_name}"]'
        else:
            lines = msp.query('LINE')
            text_query = 'TEXT MTEXT'

        for line in lines:
            pipes.append({
                'start': (line.dxf.start.x, line.dxf.start.y),
                'end': (line.dxf.end.x, line.dxf.end.y),
                'depth': 0.0,
                'radius': 50.0 # 기본값
            })

        # 텍스트 추출 (심도 및 관경)
        for text in msp.query(text_query):
            val = text.dxf.text
            texts.append({'pos': (text.dxf.insert.x, text.dxf.insert.y), 'val': val})

        # 선과 가장 가까운 텍스트 매칭
        for pipe in pipes:
            mid_x = (pipe['start'][0] + pipe['end'][0]) / 2
            mid_y = (pipe['start'][1] + pipe['end'][1]) / 2
            
            closest_depth = 1500.0 # 기본 심도
            closest_radius = 50.0  # 기본 반경
            min_dist = float('inf')

            for t in texts:
                dist = math.sqrt((mid_x - t['pos'][0])**2 + (mid_y - t['pos'][1])**2)
                if dist < min_dist:
                    min_dist = dist
                    # 텍스트에서 심도(-) 또는 관경(") 추출
                    depth_match = re.search(r'[-+]?\d*\.?\d+', t['val'])
                    if depth_match and '"' not in t['val']:
                        closest_depth = abs(float(depth_match.group()))
                    if '"' in t['val']:
                        inch_val = float(re.search(r'\d*\.?\d+', t['val']).group())
                        # 인치 -> mm 변환 후 절반(반경)
                        closest_radius = (inch_val * 25.4) / 2 

            pipe['depth'] = closest_depth
            pipe['radius'] = closest_radius

        return pipes
    except Exception as e:
        return []

# --- 3. DXF에서 시설물 추출 함수 ---
def extract_facilities(dxf_stream):
    try:
        doc = ezdxf.read(dxf_stream)
        msp = doc.modelspace()
        facilities = []
        for text in msp.query('TEXT MTEXT[layer=="2. 시설물"]'):
            facilities.append({
                "name": text.dxf.text,
                "x": text.dxf.insert.x,
                "y": text.dxf.insert.y
            })
        return facilities
    except Exception:
        return []


st.set_page_config(page_title="사외매설배관 간섭 검토 시스템", layout="wide")
st.title("🚧 지하 매설배관 굴착공사 간섭 검토 프로그램")

# --- 사이드바: 관리자 도면 업로드 ---
st.sidebar.header("🔒 [관리자용] 기준 데이터")
host_file = st.sidebar.file_uploader("당사 배관 CAD 업로드 (.dxf)", type=['dxf'])

st.subheader("👷 [공사업체용] 굴착 공사 정보 입력")

pipe_options = [
    "선택 안함", "1. 스팀 배관", "2. 도시가스 배관", "3. 수도관", 
    "4. 전력케이블 관", "5. 통신관", "6. 오수관", "7. 기타"
]
pipe_type = st.selectbox("공사(매설)할 배관의 종류를 선택해주세요:", pipe_options)
if pipe_type == "7. 기타":
    custom_pipe_type = st.text_input("구체적인 공사 배관/시설물의 종류를 작성해주세요:")

col_od, col_depth = st.columns(2)
with col_od:
    contractor_od = st.number_input("공사 배관 외경 사이즈 기입 (mm)", min_value=0.0, step=1.0)
with col_depth:
    contractor_depth = st.number_input("공사 배관 심도 기입 (관 중심 기준, mm)", min_value=0.0, step=1.0)

st.markdown("---")
st.info("💡 **[필독 주의사항]**\n\nCAD 파일 업로드 시, 공사구간에 대한 정보는 반드시 **[2D 평면 선 + 심도 텍스트 표기]** 형태로 저장된 파일로 업로드 부탁드립니다.")
is_agreed = st.checkbox("네, 위 주의사항을 확인했으며 해당 양식에 맞게 파일을 준비했습니다.")

if is_agreed:
    contractor_file = st.file_uploader("굴착 공사 구간 CAD 파일 업로드 (.dxf)", type=['dxf'], key='contractor')
    
    if contractor_file and st.button("간섭 및 이격거리 분석 실행"):
        if not host_file:
            st.error("좌측 사이드바에 [관리자용 당사 배관 CAD 파일]을 먼저 업로드해주세요.")
        elif pipe_type == "선택 안함" or contractor_od <= 0 or contractor_depth <= 0:
            st.warning("배관 종류, 외경 사이즈, 심도를 모두 정확히 입력해주세요.")
        else:
            with st.spinner("CAD 도면 교차 연산 및 주소 변환 중..."):
                final_pipe_name = custom_pipe_type if pipe_type == "7. 기타" else pipe_type
                
                # 도면 데이터 추출
                host_file.seek(0)
                contractor_file.seek(0)
                company_pipes = extract_pipes(host_file, "1. U/G Piping")
                facilities = extract_facilities(host_file)
                contractor_pipes = extract_pipes(contractor_file)
                
                report_data = []
                r_cont = contractor_od / 2
                geolocator = Nominatim(user_agent="pipe_checker_kr")
                
                point_id = 1
                
                # --- 선분 교차 및 최소 거리 연산 (Shapely 활용) ---
                for c_pipe in company_pipes:
                    line1 = LineString([c_pipe['start'], c_pipe['end']])
                    
                    for cont_pipe in contractor_pipes:
                        line2 = LineString([cont_pipe['start'], cont_pipe['end']])
                        
                        # 두 선분 사이의 중심선 거리
                        d_center = line1.distance(line2)
                        
                        # 거리가 2000mm 이내인 경우만 분석 대상(위험 의심 구역)으로 산정
                        if d_center <= 2000:
                            # 실제 교차하거나 가장 가까운 지점의 좌표 추출
                            if line1.intersects(line2):
                                inter_pt = line1.intersection(line2)
                                if isinstance(inter_pt, Point):
                                    pt_x, pt_y = inter_pt.x, inter_pt.y
                                else:
                                    pt_x, pt_y = line1.centroid.x, line1.centroid.y
                            else:
                                # 교차하지 않으면 업체 선분의 중심점을 기준점으로 잡음
                                pt_x, pt_y = line2.centroid.x, line2.centroid.y

                            # 이격거리 판정
                            d_actual = d_center - (c_pipe['radius'] + r_cont)
                            delta_z_adjusted = abs((contractor_depth + r_cont) - c_pipe['depth'])
                            
                            if d_actual > 300: status = "✅ 간섭없음"
                            elif d_actual <= 300 and delta_z_adjusted >= 300: status = "⚠️ 간섭 (보호테이프 노출)"
                            else: status = "🚨 간섭 (배관 영향 있음)"
                            
                            # CAD 좌표 -> GPS 위경도 변환
                            lon, lat = transformer.transform(pt_x, pt_y)
                            
                            # 주소 변환
                            try:
                                location = geolocator.reverse((lat, lon), exactly_one=True)
                                if location:
                                    addr = location.raw.get('address', {})
                                    do = addr.get('province', '')
                                    si = addr.get('city', addr.get('town', ''))
                                    gu = addr.get('borough', addr.get('county', ''))
                                    dong = addr.get('suburb', addr.get('neighbourhood', ''))
                                    jibun = addr.get('house_number', addr.get('residential', ''))
                                    
                                    clean_address = " ".join([p for p in [do, si, gu, dong, jibun] if p])
                                    address = clean_address if clean_address else location.address
                                else:
                                    address = "주소 변환 실패"
                            except:
                                address = "API 연결 오류"
                                
                            # 인접 시설물 탐색
                            nearest_fac = "없음"
                            min_dist = float('inf')
                            for fac in facilities:
                                dist = math.sqrt((pt_x - fac["x"])**2 + (pt_y - fac["y"])**2)
                                if dist < 10000: # 10m 이내 시설물만
                                    if dist < min_dist:
                                        min_dist = dist
                                        nearest_fac = fac["name"]
                            
                            report_data.append({
                                "검토 지점명": f"P-{point_id}",
                                "위치(주소)": address,
                                "인접 시설물": nearest_fac,
                                "실제 이격거리(mm)": round(d_actual, 1),
                                "심도 차이(mm)": round(delta_z_adjusted, 1),
                                "판정 결과": status
                            })
                            point_id += 1

                # --- 결과 출력 ---
                if not report_data:
                    st.success(f"🎉 분석 완료! 반경 2m 이내에 당사 배관과 간섭될 우려가 있는 지점이 없습니다.")
                else:
                    df_report = pd.DataFrame(report_data)
                    st.success(f"분석이 완료되었습니다. (대상: {final_pipe_name})")
                    st.markdown("### 📋 전체 간섭 검토 상세 리스트")
                    st.dataframe(df_report, use_container_width=True)

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_report.to_excel(writer, sheet_name='상세 데이터', index=False)
                    
                    st.download_button(
                        label="📥 분석 결과 엑셀 리포트 다운로드 (.xlsx)",
                        data=buffer.getvalue(),
                        file_name="배관간섭검토_분석리포트.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

else:
    st.warning("⚠️ 파일 업로드를 위해 먼저 위 안내사항을 확인하고 체크박스를 선택해주세요.")
