import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# --- 1. ตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="ระบบจัดตารางสอน - Kru Phi", layout="wide")
DATA_FILE = "school_schedule_db.json"

# ข้อมูลคาบเรียน
PERIODS = {
    1: "08.15-09.00", 2: "09.00-09.45",
    3: "10.00-10.45", 4: "10.45-11.30",
    5: "12.20-13.05", 6: "13.05-13.50",
    7: "14.00-14.45", 8: "14.45-15.30",
    9: "15.45-16.30"
}

# ข้อมูลเวลาพัก (หลังคาบที่กำหนด)
BREAKS = {
    2: "พัก<br>15 นาที",
    4: "พัก<br>กลางวัน",
    6: "พัก<br>10 นาที",
    8: "พัก<br>15 นาที"
}

# รายชื่อสายการเรียน
PROGRAM_OPTIONS = ["IEP", "EEP", "TEP", "TEP+", "SMEP", "SMEP+"]

DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]

# --- 2. ฟังก์ชันจัดการไฟล์ ---

def load_data_from_file():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            teachers_df = pd.DataFrame(data.get("teachers_data", []))
            classrooms_df = pd.DataFrame(data.get("classrooms_data", []))
            
            if classrooms_df.empty:
                classrooms_df = create_default_classrooms()

            loaded_schedule = data.get("schedule_data", {})
            current_rooms = classrooms_df["ห้องเรียน"].unique().tolist() if not classrooms_df.empty else []
            
            final_schedule = {}
            for r in current_rooms:
                final_schedule[r] = {d: {p: [] for p in range(1, 10)} for d in DAYS}
            
            for r in loaded_schedule:
                if r not in final_schedule:
                     final_schedule[r] = {d: {p: [] for p in range(1, 10)} for d in DAYS}
                for d in loaded_schedule[r]:
                    for p_str in loaded_schedule[r][d]:
                        if int(p_str) in range(1, 10):
                            final_schedule[r][d][int(p_str)] = loaded_schedule[r][d][p_str]
                            
            return final_schedule, teachers_df, classrooms_df
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None, None, None
    return None, None, None

def save_data_to_file():
    teachers_list = st.session_state.teachers_data.to_dict(orient="records")
    classrooms_list = st.session_state.classrooms_data.to_dict(orient="records")
    
    save_package = {
        "schedule_data": st.session_state.schedule_data,
        "teachers_data": teachers_list,
        "classrooms_data": classrooms_list
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(save_package, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Save failed: {e}")

def create_default_classrooms():
    default_rooms = []
    levels = ["ป.4", "ป.5", "ป.6"]
    for level in levels:
        for room in range(1, 14):
            default_rooms.append({
                "ห้องเรียน": f"{level}/{room}",
                "สายการเรียน": "IEP"
            })
    return pd.DataFrame(default_rooms)

# --- 3. เตรียมหน่วยความจำ ---
if 'data_initialized' not in st.session_state:
    loaded_sched, loaded_teach, loaded_class = load_data_from_file()
    
    if loaded_class is not None and not loaded_class.empty:
        st.session_state.classrooms_data = loaded_class
    else:
        st.session_state.classrooms_data = create_default_classrooms()
        
    current_room_list = st.session_state.classrooms_data["ห้องเรียน"].unique().tolist()

    if loaded_sched is not None:
        st.session_state.schedule_data = loaded_sched
    else:
        st.session_state.schedule_data = {
            r: {d: {p: [] for p in range(1, 10)} for d in DAYS} 
            for r in current_room_list
        }

    if loaded_teach is not None and not loaded_teach.empty:
        st.session_state.teachers_data = loaded_teach
    else:
        default_teach = [
            {"ชื่อ-สกุล": "ครูสมชาย", "วิชาที่สอน": "คณิตศาสตร์", "ระดับชั้นที่สอน": "ป.4/1"},
            {"ชื่อ-สกุล": "ครูสมหญิง", "วิชาที่สอน": "วิทยาศาสตร์", "ระดับชั้นที่สอน": "ป.5/1"},
        ]
        st.session_state.teachers_data = pd.DataFrame(default_teach)
        
    st.session_state.data_initialized = True

# Sync Schedule
current_room_list = st.session_state.classrooms_data["ห้องเรียน"].unique().tolist()
for r in current_room_list:
    if r not in st.session_state.schedule_data:
        st.session_state.schedule_data[r] = {d: {p: [] for p in range(1, 10)} for d in DAYS}

if 'confirm_needed' not in st.session_state:
    st.session_state.confirm_needed = False
if 'pending_payload' not in st.session_state:
    st.session_state.pending_payload = {}

# --- 4. ฟังก์ชันช่วย (Logic) ---

def get_all_rooms():
    return st.session_state.classrooms_data["ห้องเรียน"].unique().tolist()

def get_room_program(room_name):
    df = st.session_state.classrooms_data
    row = df[df["ห้องเรียน"] == room_name]
    if not row.empty:
        return row.iloc[0]["สายการเรียน"]
    return "-"

def get_teacher_subject(teacher_name):
    df = st.session_state.teachers_data
    row = df[df["ชื่อ-สกุล"] == teacher_name]
    if not row.empty:
        return str(row.iloc[0]["วิชาที่สอน"])
    return ""

def get_available_teachers(current_room, day, period):
    all_teachers_df = st.session_state.teachers_data
    if all_teachers_df is None or all_teachers_df.empty: return []
    all_teachers = all_teachers_df["ชื่อ-สกุล"].unique().tolist()
    busy_teachers = []
    
    all_rooms = get_all_rooms()
    for r in all_rooms:
        if r == current_room: continue
        if r in st.session_state.schedule_data:
            slots = st.session_state.schedule_data[r][day][period]
            for s in slots: busy_teachers.append(s['teacher'])
            
    return [t for t in all_teachers if t not in busy_teachers], busy_teachers

def check_fatigue(teacher_name, day, new_period, current_room):
    teaching_periods = []
    all_rooms = get_all_rooms()
    for r in all_rooms:
        if r in st.session_state.schedule_data:
            for p in range(1, 10):
                slots = st.session_state.schedule_data[r][day][p]
                for s in slots:
                    if s['teacher'] == teacher_name: teaching_periods.append(p)
    
    teaching_periods.append(new_period)
    teaching_periods = sorted(list(set(teaching_periods)))
    consecutive = 1
    max_consecutive = 1
    for i in range(1, len(teaching_periods)):
        if teaching_periods[i] == teaching_periods[i-1] + 1:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else: consecutive = 1
    return (max_consecutive <= 2), teaching_periods

def natural_sort_key(s):
    try:
        if '/' in s:
            parts = s.split('/')
            return (parts[0], int(parts[1]))
        return (s, 0)
    except:
        return (s, 0)

# --- HTML Generator (Report) ---

def generate_teacher_report_html():
    teachers = st.session_state.teachers_data["ชื่อ-สกุล"].dropna().unique().tolist()
    html = """<html><head><title>รายงานครู</title><style>
            body { font-family: 'Sarabun', 'Angsana New', sans-serif; padding: 20px; }
            h1 { text-align: center; font-size: 28px; }
            h3 { font-size: 24px; margin-bottom: 5px; }
            .section { margin-bottom: 40px; page-break-inside: avoid; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid black; padding: 5px; text-align: center; font-size: 16px; vertical-align: top; }
            th { background-color: #f0f0f0; font-weight: bold; }
            .day-col { font-weight: bold; width: 80px; font-size: 18px; }
            .break-col { background-color: #f5f5f5; color: #333; font-size: 14px; font-weight: bold; width: 40px; vertical-align: middle; }
            .page-break { page-break-after: always; }
        </style></head><body>
        <h1>รายงานตารางสอนครูรายบุคคล</h1><hr>"""
    
    for i, t_name in enumerate(teachers):
        teacher_info = st.session_state.teachers_data[st.session_state.teachers_data["ชื่อ-สกุล"] == t_name].iloc[0]
        grade_info = teacher_info.get("ระดับชั้นที่สอน", "-")
        html += f"""<div class="section"><h3>{i+1}. {t_name} <span style="font-size:0.8em; font-weight:normal;">(วิชา: {teacher_info['วิชาที่สอน']} | สอน: {grade_info})</span></h3>
            <table><thead><tr><th class="day-col">วัน</th>"""
        
        for p in range(1, 10):
            html += f"<th>{p}<br><span style='font-size:0.7em;'>{PERIODS[p]}</span></th>"
            if p in BREAKS:
                html += f"<th class='break-col'></th>"
        
        html += "</tr></thead><tbody>"
        for idx, d in enumerate(DAYS):
            html += f"<tr><td class='day-col'>{d}</td>"
            for p in range(1, 10):
                cell_content = []
                for r in get_all_rooms():
                    if r in st.session_state.schedule_data:
                        slots = st.session_state.schedule_data[r][d][p]
                        for s in slots:
                            if s['teacher'] == t_name: 
                                prog_label = f" <span style='font-size:0.8em; color:#555;'>[{s.get('program', 'รวม')}]</span>"
                                cell_content.append(f"{s['subject']}{prog_label}<br>({r})")
                if cell_content: html += f"<td>{'<hr style=`margin:2px`>'.join(cell_content)}</td>"
                else: html += "<td>-</td>"
                
                # [ROWSPAN] Break Column
                if p in BREAKS:
                    if idx == 0: # Monday only
                        html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
                    
            html += "</tr>"
        html += "</tbody></table></div><div class='page-break'></div>"
    html += "</body></html>"
    return html

def generate_grade_report_html(target_level):
    all_rooms = get_all_rooms()
    target_rooms = [r for r in all_rooms if target_level in r]
    target_rooms.sort(key=natural_sort_key)
    
    html = f"""<html><head><title>ตารางเรียน {target_level}</title><style>
            body {{ font-family: 'Sarabun', 'Angsana New', sans-serif; padding: 20px; }}
            h1 {{ text-align: center; font-size: 28px; }}
            h3 {{ font-size: 24px; margin-bottom: 5px; }}
            .section {{ margin-bottom: 40px; page-break-inside: avoid; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid black; padding: 5px; text-align: center; font-size: 16px; vertical-align: top; }}
            th {{ background-color: #e3f2fd; font-weight: bold; }}
            .day-col {{ font-weight: bold; width: 80px; font-size: 18px; }}
            .break-col {{ background-color: #f5f5f5; color: #333; font-size: 14px; font-weight: bold; width: 40px; vertical-align: middle; }}
            .page-break {{ page-break-after: always; }}
            .subject {{ font-weight: bold; font-size: 1.1em; }}
            .teacher {{ font-size: 0.9em; }}
            .prog-badge {{ font-size: 0.8em; background-color: #ddd; padding: 2px 4px; border-radius: 4px; margin-left: 4px; }}
        </style></head><body>
        <h1>ตารางเรียนระดับชั้น {target_level}</h1><p style='text-align:center'>ข้อมูล ณ {datetime.now().strftime("%d/%m/%Y %H:%M")}</p><hr>"""
    
    for room in target_rooms:
        program = get_room_program(room)
        html += f"""<div class="section"><h3>ห้องเรียน: {room} <span style="font-size:0.8em; color:#555;">(สายการเรียน: {program})</span></h3>
            <table><thead><tr><th class="day-col">วัน</th>"""
        
        for p in range(1, 10):
            html += f"<th>{p}<br><span style='font-size:0.7em;'>{PERIODS[p]}</span></th>"
            if p in BREAKS:
                html += f"<th class='break-col'></th>"

        html += "</tr></thead><tbody>"
        for idx, d in enumerate(DAYS):
            html += f"<tr><td class='day-col'>{d}</td>"
            for p in range(1, 10):
                slots = st.session_state.schedule_data[room][d][p]
                if not slots: cell = "-"
                else:
                    items = []
                    for s in slots:
                        prog_text = s.get('program', 'รวม')
                        prog_html = f"<span class='prog-badge'>{prog_text}</span>" if prog_text != "รวมทุกสาย" else ""
                        items.append(f"<div class='subject'>{s['subject']} {prog_html}</div><div class='teacher'>({s['teacher']})</div>")
                    cell = "<hr style='margin:2px'>".join(items)
                html += f"<td>{cell}</td>"
                
                # [ROWSPAN] Break Column
                if p in BREAKS:
                    if idx == 0:
                        html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
                    
            html += "</tr>"
        html += "</tbody></table></div><div class='page-break'></div>"
    html += "</body></html>"
    return html

# --- UI Renderers ---

def render_beautiful_table(grade, data_source, filter_program=None):
    html = """<style>
        table { width: 100%; border-collapse: collapse; font-family: sans-serif; background-color: #1E1E1E; color: #E0E0E0; }
        th, td { border: 1px solid #444; padding: 6px; text-align: center; vertical-align: top; }
        th { background-color: #2D2D2D; color: #FFFFFF; font-weight: bold; }
        .day-col { font-weight: bold; background-color: #262626; color: #FFD700; width: 80px;}
        .subject { font-weight: bold; color: #4FC3F7; font-size: 0.9em; }
        .teacher { font-size: 0.8em; color: #B0BEC5; margin-bottom: 2px; }
        .divider { border-top: 1px dashed #555; margin: 4px 0; }
        .empty { color: #555; }
        .program-tag { font-size: 0.75em; background-color: #FFC107; color: #000; padding: 1px 4px; border-radius: 4px; margin-left: 5px; font-weight: normal; }
        .break-col { background-color: #333; color: #AAA; font-size: 0.8em; width: 40px; vertical-align: middle; font-weight: bold;}
    </style><table><thead><tr><th class="day-col" style="color:#FFF">วัน</th>"""
    
    # Header
    for p in range(1, 10):
        html += f"<th>{p}<br><span style='font-size:0.75em; color:#AAA'>{PERIODS[p]}</span></th>"
        if p in BREAKS:
            html += "<th class='break-col'></th>"
            
    html += "</tr></thead><tbody>"
    for idx, d in enumerate(DAYS):
        html += f"<tr><td class='day-col'>{d}</td>"
        for p in range(1, 10):
            slots = data_source[grade][d][p]
            cell_items = []
            if slots:
                for s in slots:
                    prog = s.get('program', 'รวมทุกสาย')
                    if filter_program:
                        if prog == filter_program or prog == 'รวมทุกสาย':
                            prog_html = f"<span class='program-tag'>{prog}</span>" if prog != "รวมทุกสาย" else ""
                            cell_items.append(f"<div class='subject'>{s['subject']} {prog_html}</div><div class='teacher'>{s['teacher']}</div>")
                    else:
                        prog_html = f"<span class='program-tag'>{prog}</span>" if prog != "รวมทุกสาย" else ""
                        cell_items.append(f"<div class='subject'>{s['subject']} {prog_html}</div><div class='teacher'>{s['teacher']}</div>")
            if not cell_items: cell_html = "<span class='empty'>-</span>"
            else: cell_html = "<div class='divider'></div>".join(cell_items)
            html += f"<td>{cell_html}</td>"
            
            # [ROWSPAN] Break Column Data
            if p in BREAKS:
                if idx == 0: # Check if first row
                    html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
                
        html += "</tr>"
    html += "</tbody></table>"
    return html

def render_master_matrix_html(room_list, data_source):
    html = """
    <style>
        table { width: 100%; border-collapse: collapse; font-family: sans-serif; background-color: #1E1E1E; color: #E0E0E0; margin-bottom: 20px;}
        th, td { border: 1px solid #444; padding: 4px; text-align: center; vertical-align: top; font-size: 0.85em; }
        th { background-color: #333; color: #FFF; position: sticky; top: 0; z-index: 10; }
        .room-col { background-color: #2D2D2D; color: #FFD700; font-weight: bold; width: 100px; vertical-align: middle; border-bottom: 2px solid #666; }
        .day-col { background-color: #262626; color: #FFF; width: 60px; font-weight: bold; }
        .row-separator { border-bottom: 2px solid #666; }
        .subject { color: #4FC3F7; font-weight: bold; font-size: 0.95em; }
        .teacher { font-size: 0.85em; color: #B0BEC5; }
        .prog { font-size: 0.7em; background-color: #FFC107; color: #000; padding: 0 3px; border-radius: 3px; }
        .empty { color: #333; }
        .break-col { background-color: #333; color: #AAA; font-size: 0.75em; width: 40px; vertical-align: middle; font-weight: bold;}
    </style>
    <table>
    <thead>
        <tr>
            <th class="room-col">ห้องเรียน</th>
            <th class="day-col">วัน</th>
    """
    for p in range(1, 10):
        html += f"<th>{p}<br><span style='font-size:0.7em; color:#AAA'>{PERIODS[p]}</span></th>"
        if p in BREAKS:
            html += "<th class='break-col'></th>"
            
    html += "</tr></thead><tbody>"
    
    for r in room_list:
        program = get_room_program(r)
        for i, d in enumerate(DAYS):
            row_class = "row-separator" if d == "ศุกร์" else ""
            html += f"<tr class='{row_class}'>"
            if i == 0:
                html += f"<td class='room-col' rowspan='5'>{r}<br><span style='font-size:0.75em; color:#B0BEC5; font-weight:normal;'>{program}</span></td>"
            html += f"<td class='day-col'>{d}</td>"
            for p in range(1, 10):
                if r in data_source:
                    slots = data_source[r][d][p]
                    if not slots: cell_html = "<span class='empty'>-</span>"
                    else:
                        items = []
                        for s in slots:
                            prog_item = s.get('program', '')
                            prog_html = f"<span class='prog'>{prog_item}</span>" if prog_item != "รวมทุกสาย" else ""
                            items.append(f"<div><span class='subject'>{s['subject']}</span> {prog_html}<br><span class='teacher'>{s['teacher']}</span></div>")
                        cell_html = "<hr style='margin:2px; border-color:#444;'>".join(items)
                else: cell_html = "-"
                html += f"<td>{cell_html}</td>"
                
                # [ROWSPAN] Break Column for Master View
                # Note: In Master View, each room has 5 rows. So rowspan=5 logic applies per room block.
                if p in BREAKS:
                    if i == 0:
                        html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
            html += "</tr>"
    html += "</tbody></table>"
    return html

# --- 5. หน้าจอหลัก (เมนู) ---
menu = st.sidebar.radio("เมนูหลัก", [
    "1. 🗓️ ตารางเรียนรวม (Master View)",
    "2. 📅 จัดตารางสอน", 
    "3. 👥 ข้อมูลของครู", 
    "4. 🏫 ข้อมูลห้องเรียน", 
    "5. 🖨️ ระบบรายงาน",
    "6. 📊 Dashboard สรุปยอด"
])

# ==========================================
# เมนู 1: Master View
# ==========================================
if menu == "1. 🗓️ ตารางเรียนรวม (Master View)":
    st.header("🗓️ ตารางเรียนรวม (Master Schedule View)")
    st.info("💡 เลือก 'ระดับชั้น' ด้านล่าง ระบบจะแสดงตารางรวมของห้องเรียนทุกห้องในระดับชั้นนั้น พร้อมกัน 5 วันครับ")
    
    all_rooms = get_all_rooms()
    unique_levels = sorted(list(set([r.split('/')[0] for r in all_rooms if '/' in r])))
    
    if not unique_levels:
        st.warning("ยังไม่มีข้อมูลห้องเรียนในระบบ")
    else:
        sel_master_level = st.selectbox("เลือกระดับชั้นที่ต้องการดู:", unique_levels)
        target_rooms = [r for r in all_rooms if r.startswith(sel_master_level)]
        target_rooms.sort(key=natural_sort_key) 
        st.markdown("---")
        master_html = render_master_matrix_html(target_rooms, st.session_state.schedule_data)
        st.markdown(master_html, unsafe_allow_html=True)

# ==========================================
# เมนู 2: จัดตารางสอน
# ==========================================
elif menu == "2. 📅 จัดตารางสอน":
    st.header("จัดตารางสอน (Auto-Save 💾)")
    
    current_rooms_list = get_all_rooms()
    if not current_rooms_list:
        st.warning("⚠️ ยังไม่มีข้อมูลห้องเรียน กรุณาไปเพิ่มที่เมนู 'ข้อมูลห้องเรียน' ก่อนครับ")
    else:
        selected_grade = st.selectbox("เลือกห้องเรียน:", current_rooms_list)
        program_str = get_room_program(selected_grade)
        
        st.caption(f"🎓 สายการเรียน: **{program_str}**")
        st.markdown("---")

        # 1. Edit Section
        st.subheader("📝 แก้ไข/ลงตารางเรียน")
        programs_list = [p.strip() for p in str(program_str).split(",") if p.strip()]
        target_prog_options = ["รวมทุกสาย"] + programs_list
        
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1.5, 1.2, 1])
        with col1: sel_day = st.selectbox("1. เลือกวัน", DAYS)
        with col2: 
            period_opts = {k: f"{k} ({v})" for k, v in PERIODS.items()}
            sel_period = st.selectbox("2. เลือกเวลา", list(PERIODS.keys()), format_func=lambda x: period_opts[x])
        with col3:
            available_teachers, busy_list = get_available_teachers(selected_grade, sel_day, sel_period)
            options = ["-- เลือกครู --"] + available_teachers
            sel_teacher = st.selectbox("3. เลือกครู (เฉพาะที่ว่าง)", options)
        with col4: 
            sel_target_prog = st.selectbox("4. สอนสายไหน?", target_prog_options)
            current_slots = st.session_state.schedule_data[selected_grade][sel_day][sel_period]
            if len(current_slots) == 0: st.info("ℹ️ ว่าง")
            elif len(current_slots) == 1: st.warning(f"ℹ️ มี 1 วิชา")
            else: st.error("⛔ เต็มแล้ว")
        with col5:
            st.write(""); st.write("")
            btn_add = st.button("➕ เพิ่ม", type="primary", use_container_width=True)
            btn_clear = st.button("🗑️ ล้าง", type="secondary", use_container_width=True)
            
        if btn_clear:
            st.session_state.schedule_data[selected_grade][sel_day][sel_period] = []
            save_data_to_file()
            st.success("ล้างข้อมูลเรียบร้อย"); st.rerun()
            
        if btn_add:
            if sel_teacher == "-- เลือกครู --": st.error("กรุณาเลือกชื่อครูก่อน")
            elif len(st.session_state.schedule_data[selected_grade][sel_day][sel_period]) >= 2: st.error("❌ เต็มแล้ว (Max 2)")
            else:
                is_safe, periods_list = check_fatigue(sel_teacher, sel_day, sel_period, selected_grade)
                entry_data = {"teacher": sel_teacher, "subject": get_teacher_subject(sel_teacher), "program": sel_target_prog}
                if is_safe:
                    st.session_state.schedule_data[selected_grade][sel_day][sel_period].append(entry_data)
                    save_data_to_file()
                    st.success(f"✅ เพิ่มสำเร็จ ({sel_target_prog})"); st.rerun()
                else:
                    st.session_state.confirm_needed = True
                    st.session_state.pending_payload = {"entry_data": entry_data, "grade": selected_grade, "day": sel_day, "period": sel_period, "periods_list": periods_list, "teacher": sel_teacher}
        if st.session_state.confirm_needed:
            payload = st.session_state.pending_payload
            st.warning(f"⚠️ **แจ้งเตือน:** ครู {payload['teacher']} สอนติดกันเกิน 2 คาบแล้ว ({payload['periods_list']})")
            c1, c2 = st.columns(2)
            if c1.button("✅ ยืนยัน"):
                g, d, p = payload['grade'], payload['day'], payload['period']
                st.session_state.schedule_data[g][d][p].append(payload['entry_data'])
                save_data_to_file(); st.session_state.confirm_needed = False; st.success("บันทึกเรียบร้อย"); st.rerun()
            if c2.button("❌ ยกเลิก"): st.session_state.confirm_needed = False; st.rerun()

        st.markdown("---")

        # 2. Reset Button
        with st.expander("🗑️ ล้างตารางสอนทั้งหมดของห้องนี้ (Reset)"):
            st.warning(f"⚠️ คำเตือน: คุณกำลังจะลบข้อมูลตารางสอนทั้งหมดของ **ห้อง {selected_grade}** การกระทำนี้ไม่สามารถย้อนกลับได้")
            if st.button("ยืนยันการล้างข้อมูลห้องนี้", type="primary"):
                for d in DAYS:
                    for p in range(1, 10):
                        st.session_state.schedule_data[selected_grade][d][p] = []
                save_data_to_file()
                st.success(f"ล้างข้อมูลห้อง {selected_grade} เรียบร้อยแล้ว")
                st.rerun()
        
        # 3. Schedule Table
        st.subheader(f"👀 ตารางเรียนรวม: {selected_grade}")
        html_table = render_beautiful_table(selected_grade, st.session_state.schedule_data)
        st.markdown(html_table, unsafe_allow_html=True)
        
        # 4. Split Tables
        if len(programs_list) > 1:
            st.markdown("---")
            st.info(f"📂 ห้องนี้มี **{len(programs_list)} สายการเรียน** ระบบจึงแสดงตารางแยกด้านล่าง")
            for prog in programs_list:
                st.write("")
                st.subheader(f"🔷 ตารางเรียนสำหรับสาย: {prog}")
                st.markdown(render_beautiful_table(selected_grade, st.session_state.schedule_data, filter_program=prog), unsafe_allow_html=True)

# ==========================================
# เมนู 3: ข้อมูลของครู
# ==========================================
elif menu == "3. 👥 ข้อมูลของครู":
    st.header("จัดการข้อมูลครูผู้สอน")
    current_rooms_list = get_all_rooms()
    existing_names = st.session_state.teachers_data["ชื่อ-สกุล"].tolist()
    option_list = ["-- เพิ่มครูคนใหม่ --"] + existing_names
    
    st.subheader("✏️ เพิ่ม / แก้ไข ข้อมูลครู")
    selected_option = st.selectbox("เลือกครูที่ต้องการแก้ไข:", option_list)
    
    default_name, default_subject, default_rooms = "", "", []
    if selected_option != "-- เพิ่มครูคนใหม่ --":
        row = st.session_state.teachers_data[st.session_state.teachers_data["ชื่อ-สกุล"] == selected_option].iloc[0]
        default_name = row["ชื่อ-สกุล"]
        default_subject = row["วิชาที่สอน"]
        rooms_str = str(row["ระดับชั้นที่สอน"])
        if rooms_str and rooms_str != "nan":
            default_rooms = [r.strip() for r in rooms_str.split(",") if r.strip() in current_rooms_list]
    
    with st.form("teacher_form"):
        col1, col2 = st.columns(2)
        with col1: input_name = st.text_input("ชื่อ-สกุล", value=default_name)
        with col2: input_subject = st.text_input("วิชาที่สอน", value=default_subject)
        input_rooms = st.multiselect("เลือกระดับชั้น/ห้องที่สอน", options=current_rooms_list, default=default_rooms)
        submitted = st.form_submit_button("💾 บันทึกข้อมูล")
        if submitted:
            if not input_name: st.error("กรุณากรอกชื่อครู")
            else:
                rooms_string = ", ".join(input_rooms)
                df = st.session_state.teachers_data
                if input_name in df["ชื่อ-สกุล"].values and selected_option == input_name:
                    df.loc[df["ชื่อ-สกุล"] == input_name, "วิชาที่สอน"] = input_subject
                    df.loc[df["ชื่อ-สกุล"] == input_name, "ระดับชั้นที่สอน"] = rooms_string
                    st.success(f"✅ อัปเดตข้อมูล {input_name} เรียบร้อย")
                elif input_name in df["ชื่อ-สกุล"].values and selected_option == "-- เพิ่มครูคนใหม่ --":
                    st.error("ชื่อครูซ้ำ")
                else:
                    new_row = pd.DataFrame([{"ชื่อ-สกุล": input_name, "วิชาที่สอน": input_subject, "ระดับชั้นที่สอน": rooms_string}])
                    st.session_state.teachers_data = pd.concat([df, new_row], ignore_index=True)
                    st.success(f"✅ เพิ่มครูใหม่ {input_name} เรียบร้อย")
                save_data_to_file()
                st.rerun()
    if selected_option != "-- เพิ่มครูคนใหม่ --":
        if st.button("🗑️ ลบครูท่านนี้", type="secondary"):
             st.session_state.teachers_data = st.session_state.teachers_data[st.session_state.teachers_data["ชื่อ-สกุล"] != selected_option]
             save_data_to_file()
             st.success("ลบเรียบร้อย"); st.rerun()

    st.markdown("---")
    st.subheader("📋 รายชื่อครูในระบบ")
    st.dataframe(st.session_state.teachers_data, use_container_width=True)

# ==========================================
# เมนู 4: ข้อมูลห้องเรียน
# ==========================================
elif menu == "4. 🏫 ข้อมูลห้องเรียน":
    st.header("จัดการข้อมูลห้องเรียน")
    existing_rooms = st.session_state.classrooms_data["ห้องเรียน"].tolist()
    room_option_list = ["-- เพิ่มห้องใหม่ --"] + existing_rooms
    
    st.subheader("✏️ เพิ่ม / แก้ไข ห้องเรียน")
    selected_room_opt = st.selectbox("เลือกห้องที่ต้องการแก้ไข:", room_option_list)
    
    default_room_name = ""
    default_programs = []
    
    if selected_room_opt != "-- เพิ่มห้องใหม่ --":
        row = st.session_state.classrooms_data[st.session_state.classrooms_data["ห้องเรียน"] == selected_room_opt].iloc[0]
        default_room_name = row["ห้องเรียน"]
        prog_str = str(row["สายการเรียน"])
        if prog_str and prog_str != "nan":
            default_programs = [p.strip() for p in prog_str.split(",") if p.strip() in PROGRAM_OPTIONS]
            
    with st.form("classroom_form"):
        col1, col2 = st.columns([1, 2])
        with col1:
            input_room_name = st.text_input("ชื่อห้องเรียน (เช่น ป.4/1)", value=default_room_name)
        with col2:
            input_programs = st.multiselect("สายการเรียน", options=PROGRAM_OPTIONS, default=default_programs)
        submitted = st.form_submit_button("💾 บันทึกข้อมูลห้องเรียน")
        
        if submitted:
            if not input_room_name: st.error("กรุณากรอกชื่อห้องเรียน")
            elif not input_programs: st.error("กรุณาเลือกสายการเรียนอย่างน้อย 1 อย่าง")
            else:
                programs_str = ", ".join(input_programs)
                df = st.session_state.classrooms_data
                if input_room_name in df["ห้องเรียน"].values and selected_room_opt == input_room_name:
                    df.loc[df["ห้องเรียน"] == input_room_name, "สายการเรียน"] = programs_str
                    st.success(f"✅ อัปเดตห้อง {input_room_name} เรียบร้อย")
                elif input_room_name in df["ห้องเรียน"].values and selected_room_opt == "-- เพิ่มห้องใหม่ --":
                    st.error("ชื่อห้องเรียนซ้ำ")
                else:
                    new_row = pd.DataFrame([{"ห้องเรียน": input_room_name, "สายการเรียน": programs_str}])
                    st.session_state.classrooms_data = pd.concat([df, new_row], ignore_index=True)
                    st.success(f"✅ เพิ่มห้อง {input_room_name} เรียบร้อย")
                save_data_to_file()
                st.rerun()
    if selected_room_opt != "-- เพิ่มห้องใหม่ --":
        if st.button("🗑️ ลบห้องเรียนนี้", type="secondary"):
             st.session_state.classrooms_data = st.session_state.classrooms_data[st.session_state.classrooms_data["ห้องเรียน"] != selected_room_opt]
             save_data_to_file()
             st.success("ลบเรียบร้อย"); st.rerun()

    st.markdown("---")
    st.subheader("📋 รายชื่อห้องเรียนในระบบ")
    st.dataframe(st.session_state.classrooms_data, use_container_width=True)

# ==========================================
# เมนู 5: ระบบรายงาน
# ==========================================
elif menu == "5. 🖨️ ระบบรายงาน":
    st.header("ระบบออกรายงาน (Print/PDF)")
    tab_teacher, tab_grade = st.tabs(["📄 Report ครูรายคน", "🏫 Report ระดับชั้น"])
    
    with tab_teacher:
        st.subheader("รายงานตารางสอนรายบุคคล (ครู)")
        html_report_teacher = generate_teacher_report_html()
        st.download_button("📥 ดาวน์โหลด Report ครูทั้งหมด", data=html_report_teacher, file_name="teacher_schedule.html", mime="text/html", type="primary")
        st.markdown("---")
        t_list = st.session_state.teachers_data["ชื่อ-สกุล"].unique().tolist()
        if t_list:
            sel_t = st.selectbox("เลือกครูเพื่อดูตัวอย่าง:", t_list, key="rep_t")
            temp_data = { "Report": { d: { p: [] for p in range(1, 10) } for d in DAYS } }
            for d in DAYS:
                for p in range(1, 10):
                    for g in get_all_rooms():
                        if g in st.session_state.schedule_data:
                            slots = st.session_state.schedule_data[g][d][p]
                            for s in slots:
                                if s['teacher'] == sel_t: temp_data["Report"][d][p].append({"subject": s['subject'], "teacher": f"({g})"})
            st.markdown(render_beautiful_table("Report", temp_data), unsafe_allow_html=True)

    with tab_grade:
        st.subheader("รายงานตารางเรียนรายระดับชั้น")
        col_g1, col_g2 = st.columns([1, 2])
        with col_g1: sel_level = st.text_input("ค้นหาระดับชั้น (เช่น ป.4)", value="ป.4")
        with col_g2:
            st.write(""); st.write("")
            if sel_level:
                html_report_grade = generate_grade_report_html(sel_level)
                st.download_button(f"📥 ดาวน์โหลด Report ({sel_level})", data=html_report_grade, file_name=f"grade_{sel_level}_report.html", mime="text/html", type="primary")
        if sel_level:
            st.markdown("---")
            st.write(f"**ตัวอย่างห้องที่พบ:**")
            found_rooms = [r for r in get_all_rooms() if sel_level in r]
            if found_rooms:
                example_room = found_rooms[0]
                prog = get_room_program(example_room)
                st.markdown(f"**ห้อง: {example_room} (สาย: {prog})**")
                st.markdown(render_beautiful_table(example_room, st.session_state.schedule_data), unsafe_allow_html=True)
            else:
                st.warning("ไม่พบห้องเรียนที่ค้นหา")

# ==========================================
# เมนู 6: Dashboard
# ==========================================
elif menu == "6. 📊 Dashboard สรุปยอด":
    st.header("Dashboard สรุปภาระงานสอน")
    
    all_rooms_list = get_all_rooms()
    unique_levels = sorted(list(set([r.split('/')[0] for r in all_rooms_list if '/' in r])))
    
    filter_options = ["ภาพรวมทั้งโรงเรียน"] + unique_levels
    selected_filter = st.selectbox("🔍 เลือกดูข้อมูลเฉพาะระดับชั้น:", filter_options)
    
    teacher_counts = {}
    
    if selected_filter == "ภาพรวมทั้งโรงเรียน":
        all_teachers = st.session_state.teachers_data["ชื่อ-สกุล"].tolist()
        for t in all_teachers: teacher_counts[t] = 0
    
    total_slots = 0
    
    schedule_data = st.session_state.schedule_data
    for room in schedule_data:
        if selected_filter != "ภาพรวมทั้งโรงเรียน":
            if not room.startswith(selected_filter):
                continue

        for day in DAYS:
            for period in range(1, 10):
                slots = schedule_data[room][day][period]
                for s in slots:
                    t_name = s['teacher']
                    if t_name in teacher_counts:
                        teacher_counts[t_name] += 1
                    else:
                        teacher_counts[t_name] = 1 
                    total_slots += 1

    c1, c2, c3 = st.columns(3)
    c1.metric("จำนวนครู (ในขอบเขตนี้)", f"{len(teacher_counts)} คน")
    c2.metric(f"ยอดสอนรวม ({selected_filter})", f"{total_slots} คาบ")
    
    st.markdown("---")
    
    if teacher_counts:
        df_stats = pd.DataFrame(list(teacher_counts.items()), columns=["ชื่อครู", "จำนวนคาบ/สัปดาห์"])
        df_stats = df_stats.sort_values(by="จำนวนคาบ/สัปดาห์", ascending=False).reset_index(drop=True)
        
        st.subheader(f"📊 กราฟแสดงจำนวนคาบสอน ({selected_filter})")
        st.bar_chart(df_stats.set_index("ชื่อครู"))
        
        st.markdown("---")
        
        st.subheader("📋 ตารางจัดลำดับภาระงาน")
        st.dataframe(
            df_stats, 
            column_config={
                "จำนวนคาบ/สัปดาห์": st.column_config.ProgressColumn(
                    "จำนวนคาบ", 
                    format="%d", 
                    min_value=0, 
                    max_value=30
                )
            },
            use_container_width=True
        )
    else:
        st.warning("ไม่พบข้อมูลการสอนในระดับชั้นที่เลือก")