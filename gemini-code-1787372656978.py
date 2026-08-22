import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="사외매설배관 간섭 검토 시스템", layout="wide")
st.title("🚧 지하 매설배관 굴착공사 간섭 검토 프로그램")

st.subheader("👷 [공사업체용] 굴착 공사 정보 입력")

# 1. 배관 종류 선택 (7가지 + 기타)
pipe_options = [
    "선택 안함", "1. 스팀 배관", "2. 도시가스 배관", "3. 수도관", 
    "4. 전력케이블 관", "5. 통신관", "6. 오수관", "7. 기타"
]
pipe_type = st.selectbox("공사(매설)할 배관의 종류를 선택해주세요:", pipe_options)

if pipe_type == "7. 기타":
    custom_pipe_type = st.text_input("구체적인 공사 배관/시설물의 종류를 작성해주세요:")

# 2. 업체 배관 제원 입력 (명칭 명확화)
col_od, col_depth = st.columns(2)
with col_od:
    contractor_od = st.number_input("공사 배관 외경 사이즈 기입 (mm)", min_value=0.0, step=1.0)
with col_depth:
    contractor_depth = st.number_input("공사 배관 심도 기입 (관 중심 기준, mm)", min_value=0.0, step=1.0)

st.markdown("---")

# 3. 파일 업로드 안전장치
st.info("💡 **[필독 주의사항]**\n\nCAD 파일 업로드 시, 공사구간에 대한 정보는 반드시 **[2D 평면 선 + 심도 텍스트 표기]** 형태로 저장된 파일로 업로드 부탁드립니다.")
is_agreed = st.checkbox("네, 위 주의사항을 확인했으며 해당 양식에 맞게 파일을 준비했습니다.")

if is_agreed:
    contractor_file = st.file_uploader("굴착 공사 구간 CAD 파일 업로드 (.dxf)", type=['dxf'], key='contractor')
    
    if contractor_file and st.button("간섭 및 이격거리 분석 실행"):
        if pipe_type == "선택 안함" or contractor_od <= 0 or contractor_depth <= 0:
            st.warning("배관 종류, 외경 사이즈, 심도를 모두 정확히 입력해주세요.")
        else:
            with st.spinner("법적 이격거리(300mm) 기준 간섭 여부 분석 중..."):
                final_pipe_name = custom_pipe_type if pipe_type == "7. 기타" else pipe_type
                
                # --- 실제 환경에서는 여기서 CAD 파일을 읽고 교차점을 찾는 로직이 실행됩니다 ---
                # 임시 분석 결과 데이터 (더미 데이터)
                clash_points = [
                    {"point": "P-1", "d_center": 400.0, "company_depth": 1500.0, "r_comp": 108.15},
                    {"point": "P-2", "d_center": 350.0, "company_depth": 1000.0, "r_comp": 108.15},
                    {"point": "P-3", "d_center": 250.0, "company_depth": 1500.0, "r_comp": 108.15}
                ]
                
                report_data = []
                r_cont = contractor_od / 2  # 업체 배관 외경 절반
                
                for cp in clash_points:
                    # 1) 실제 평면 이격거리 계산
                    d_actual = cp["d_center"] - (cp["r_comp"] + r_cont)
                    
                    # 2) 실제 수직(심도) 차이 계산 (업체 심도 + 업체 배관 반경 - 당사 배관 심도)
                    delta_z_adjusted = abs((contractor_depth + r_cont) - cp["company_depth"])
                    
                    # 3) 판정 로직
                    if d_actual > 300:
                        status = "✅ 간섭없음 (배관 없음)"
                    elif d_actual <= 300 and delta_z_adjusted >= 300:
                        status = "⚠️ 간섭 (배관 영향 없음, 보호테이프 노출 예정)"
                    else:
                        status = "🚨 간섭 (배관 영향 있음)"
                        
                    report_data.append({
                        "검토 지점": cp["point"],
                        "기준선 간 거리(mm)": cp["d_center"],
                        "실제 이격거리(mm)": round(d_actual, 1),
                        "심도 차이(mm)": round(delta_z_adjusted, 1),
                        "판정 결과": status
                    })
                
                # 데이터 프레임 변환
                df_report = pd.DataFrame(report_data)
                
                # --- 화면 출력 ---
                st.success(f"분석이 완료되었습니다. (대상: {final_pipe_name})")
                st.markdown("### 📋 전체 간섭 검토 상세 리스트")
                st.dataframe(df_report, use_container_width=True)
                
                # --- 엑셀 다운로드 기능 ---
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