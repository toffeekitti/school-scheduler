import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# --- 1. ตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="ระบบจัดตารางสอนออนไลน์ - Kru Phi", layout="wide")

# เชื่อมต่อ Google Sheets
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

SHEET_NAME = "SchoolSchedulerDB"

PERIODS = {
    1: "08.15-09.00", 2: "09.00-09.45",
    3: "10.00-10.45", 4: "10.45-11.30",
    5: "12.20-13.05", 6: "13.05-13.50",
    7: "14.00-14.45", 8: "14.45-15.30",
    9: "15.45-16.30"
}
BREAKS = {
    2: "พัก<br>15 นาที", 4: "พัก<br>กลางวัน",
    6: "พัก<br>10 นาที", 8: "พัก<br>15 นาที"
}
PROGRAM_OPTIONS = ["IEP", "EEP", "TEP", "TEP+", "SMEP", "SMEP+"]
DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]

# --- 2. ฟังก์ชันจัดการข้อมูล ---

def load_data_from_gsheets():
    try:
        client = init_connection()
        sh = client.open(SHEET_NAME)
        
        w_teach = sh.worksheet("Teachers")
        teachers_data = w_teach.get_all_records()
        teachers_df = pd.DataFrame(teachers_data)
        
        w_class = sh.worksheet("Classrooms")
        class_data = w_class.get_all_records()
        classrooms_df = pd.DataFrame(class_data)
        
        if classrooms_df.empty:
            classrooms_df = create_default_classrooms()
            
        try:
            w_sched = sh.worksheet("Schedule")
            sched_records = w_sched.get_all_records()
        except:
            sched_records = []
            
        current_rooms = classrooms_df["ห้องเรียน"].unique().tolist()
        final_schedule = {r: {d: {p: [] for p in range(1, 10)} for d in DAYS} for r in current_rooms}
        
        for row in sched_records:
            r = row['Room']
            d = row['Day']
            p = int(row['Period'])
            if r in final_schedule and d in DAYS and p in range(1, 10):
                final_schedule[r][d][p].append({
                    "teacher": row['Teacher'],
                    "subject": row['Subject'],
                    "program": row['Program']
                })
                
        return final_schedule, teachers_df, classrooms_df
        
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {e}")
        st.stop()
        return None, None, None

def save_data_to_gsheets():
    try:
        client = init_connection()
        sh = client.open(SHEET_NAME)
        
        w_teach = sh.worksheet("Teachers")
        w_teach.clear()
        if not st.session_state.teachers_data.empty:
            t_data = [st.session_state.teachers_data.columns.tolist()] + st.session_state.teachers_data.astype(str).values.tolist()
            w_teach.update(t_data)
            
        w_class = sh.worksheet("Classrooms")
        w_class.clear()
        if not st.session_state.classrooms_data.empty:
            c_data = [st.session_state.classrooms_data.columns.tolist()] + st.session_state.classrooms_data.astype(str).values.tolist()
            w_class.update(c_data)
            
        w_sched = sh.worksheet("Schedule")
        w_sched.clear()
        
        flat_data = []
        headers = ["Room", "Day", "Period", "Teacher", "Subject", "Program"]
        flat_data.append(headers)
        
        sched = st.session_state.schedule_data
        for r in sched:
            for d in sched[r]:
                for p in sched[r][d]:
                    for slot in sched[r][d][p]:
                        flat_data.append([
                            str(r), str(d), int(p), 
                            str(slot['teacher']), str(slot['subject']), str(slot.get('program', 'รวม'))
                        ])
        
        w_sched.update(flat_data)
        
    except Exception as e:
        st.error(f"⛔ บันทึก Google Sheets ไม่สำเร็จ: {e}")
        st.stop()

def create_default_classrooms():
    default_rooms = []
    levels = ["ป.4", "ป.5", "ป.6"]
    for level in levels:
        for room in range(1, 14):
            default_rooms.append({"ห้องเรียน": f"{level}/{room}", "สายการเรียน": "IEP"})
    return pd.DataFrame(default_rooms)

# --- 3. เตรียมหน่วยความจำ ---
if 'data_initialized' not in st.session_state:
    with st.spinner('กำลังโหลดข้อมูลจาก Google Sheets...'):
        loaded_sched, loaded_teach, loaded_class = load_data_from_gsheets()
    
    if loaded_sched is not None:
        st.session_state.schedule_data = loaded_sched
        st.session_state.teachers_data = loaded_teach
        st.session_state.classrooms_data = loaded_class
    else:
        st.session_state.classrooms_data = create_default_classrooms()
        current_rooms = st.session_state.classrooms_data["ห้องเรียน"].unique().tolist()
        st.session_state.schedule_data = {r: {d: {p: [] for p in range(1, 10)} for d in DAYS} for r in current_rooms}
        st.session_state.teachers_data = pd.DataFrame([{"ชื่อ-สกุล": "ครูตัวอย่าง", "วิชาที่สอน": "ทดสอบ", "ระดับชั้นที่สอน": "-"}])
        
    st.session_state.data_initialized = True

if 'marathon_confirm_data' not in st.session_state:
    st.session_state.marathon_confirm_data = None

# --- 4. Helper Functions ---
def get_all_rooms():
    if st.session_state.classrooms_data.empty: return []
    return st.session_state.classrooms_data["ห้องเรียน"].unique().tolist()

def get_room_program(room_name):
    df = st.session_state.classrooms_data
    row = df[df["ห้องเรียน"] == room_name]
    if not row.empty: return row.iloc[0]["สายการเรียน"]
    return "-"

def get_teacher_subject(teacher_name):
    df = st.session_state.teachers_data
    row = df[df["ชื่อ-สกุล"] == teacher_name]
    if not row.empty: return str(row.iloc[0]["วิชาที่สอน"])
    return ""

def is_teacher_assigned_to_room(teacher_name, room_name):
    df = st.session_state.teachers_data
    row = df[df["ชื่อ-สกุล"] == teacher_name]
    if row.empty: return False
    assigned_str = str(row.iloc[0]["ระดับชั้นที่สอน"])
    if assigned_str == "-" or assigned_str == "nan" or not assigned_str.strip():
        return True 
    assigned_list = [r.strip() for r in assigned_str.split(",")]
    return room_name in assigned_list

def get_available_teachers(current_room, day, period):
    all_teachers_df = st.session_state.teachers_data
    if all_teachers_df is None or all_teachers_df.empty: return [], []
    all_teachers = all_teachers_df["ชื่อ-สกุล"].unique().tolist()
    busy_teachers = []
    
    all_rooms = get_all_rooms()
    for r in all_rooms:
        if r == current_room: continue
        if r in st.session_state.schedule_data:
            slots = st.session_state.schedule_data[r][day][period]
            for s in slots:
                busy_teachers.append(s['teacher'])
    
    available = []
    for t in all_teachers:
        if t not in busy_teachers:
            if is_teacher_assigned_to_room(t, current_room):
                available.append(t)
                
    return available, busy_teachers

def validate_marathon_teaching(schedule_updates, current_room, day):
    conflicts = []
    involved_teachers = set(schedule_updates.values())
    involved_teachers.discard(None)
    involved_teachers.discard("-- ว่าง --")
    all_rooms = get_all_rooms()
    for teacher in involved_teachers:
        teaching_periods = []
        for r in all_rooms:
            if r == current_room: continue 
            for p in range(1, 10):
                slots = st.session_state.schedule_data[r][day][p]
                for s in slots:
                    if s['teacher'] == teacher:
                        teaching_periods.append(p)
        for p, selected_t in schedule_updates.items():
            if selected_t == teacher:
                teaching_periods.append(p)
        teaching_periods = sorted(list(set(teaching_periods)))
        consecutive = 1
        max_consecutive = 1
        for i in range(1, len(teaching_periods)):
            if teaching_periods[i] == teaching_periods[i-1] + 1:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 1
        if max_consecutive > 2:
            conflicts.append(f"⚠️ ครู {teacher} สอนติดกัน {max_consecutive} คาบ (คาบ {teaching_periods})")
    return conflicts

def apply_schedule_updates(grade, day, new_data, target_prog):
    for p, new_teacher in new_data.items():
        current_slots = st.session_state.schedule_data[grade][day][p]
        kept_slots = [s for s in current_slots if s.get('program', 'รวมทุกสาย') != target_prog]
        if new_teacher != "-- ว่าง --":
            subj = get_teacher_subject(new_teacher)
            new_slot = {"teacher": new_teacher, "subject": subj, "program": target_prog}
            kept_slots.append(new_slot)
        st.session_state.schedule_data[grade][day][p] = kept_slots
    save_data_to_gsheets()

def natural_sort_key(s):
    try:
        if '/' in s: parts = s.split('/'); return (parts[0], int(parts[1]))
        return (s, 0)
    except: return (s, 0)

# --- 5. UI Renderers ---
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
    for p in range(1, 10):
        html += f"<th>{p}<br><span style='font-size:0.75em; color:#AAA'>{PERIODS[p]}</span></th>"
        if p in BREAKS: html += "<th class='break-col'></th>"
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
            if p in BREAKS:
                if idx == 0: html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
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
    <table><thead><tr><th class="room-col">ห้องเรียน</th><th class="day-col">วัน</th>"""
    for p in range(1, 10):
        html += f"<th>{p}<br><span style='font-size:0.7em; color:#AAA'>{PERIODS[p]}</span></th>"
        if p in BREAKS: html += "<th class='break-col'></th>"
    html += "</tr></thead><tbody>"
    for r in room_list:
        program = get_room_program(r)
        for i, d in enumerate(DAYS):
            row_class = "row-separator" if d == "ศุกร์" else ""
            html += f"<tr class='{row_class}'>"
            if i == 0: html += f"<td class='room-col' rowspan='5'>{r}<br><span style='font-size:0.75em; color:#B0BEC5; font-weight:normal;'>{program}</span></td>"
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
                if p in BREAKS:
                    if i == 0: html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
            html += "</tr>"
    html += "</tbody></table>"
    return html

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
        </style></head><body><h1>รายงานตารางสอนครูรายบุคคล</h1><hr>"""
    for i, t_name in enumerate(teachers):
        teacher_info = st.session_state.teachers_data[st.session_state.teachers_data["ชื่อ-สกุล"] == t_name].iloc[0]
        grade_info = teacher_info.get("ระดับชั้นที่สอน", "-")
        html += f"""<div class="section"><h3>{i+1}. {t_name} <span style="font-size:0.8em; font-weight:normal;">(วิชา: {teacher_info['วิชาที่สอน']} | สอน: {grade_info})</span></h3>
            <table><thead><tr><th class="day-col">วัน</th>"""
        for p in range(1, 10):
            html += f"<th>{p}<br><span style='font-size:0.7em;'>{PERIODS[p]}</span></th>"
            if p in BREAKS: html += f"<th class='break-col'></th>"
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
                if p in BREAKS:
                    if idx == 0: html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
            html += "</tr>"
        html += "</tbody></table></div><div class='page-break'></div>"
    html += "</body></html>"
    return html

# --- [UPDATED] Report Logic: Master + Separate Tables ---
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
        </style></head><body><h1>ตารางเรียนระดับชั้น {target_level}</h1><p style='text-align:center'>ข้อมูล ณ {datetime.now().strftime("%d/%m/%Y %H:%M")}</p><hr>"""
    
    for room in target_rooms:
        program_str = get_room_program(room)
        programs_list = [p.strip() for p in str(program_str).split(",") if p.strip()]
        if not programs_list: programs_list = ["รวมทุกสาย"]
        
        # --- 1. MASTER TABLE (ตารางรวม) ---
        html += f"""<div class="section"><h3>ห้องเรียน: {room} (ตารางรวมทุกสาย)</h3>
            <table><thead><tr><th class="day-col">วัน</th>"""
        for p in range(1, 10):
            html += f"<th>{p}<br><span style='font-size:0.7em;'>{PERIODS[p]}</span></th>"
            if p in BREAKS: html += f"<th class='break-col'></th>"
        html += "</tr></thead><tbody>"
        for idx, d in enumerate(DAYS):
            html += f"<tr><td class='day-col'>{d}</td>"
            for p in range(1, 10):
                slots = st.session_state.schedule_data[room][d][p]
                cell_items = []
                if slots:
                    for s in slots:
                        prog_text = s.get('program', 'รวม')
                        prog_html = f"<span class='prog-badge'>{prog_text}</span>" if prog_text != "รวมทุกสาย" else ""
                        cell_items.append(f"<div class='subject'>{s['subject']} {prog_html}</div><div class='teacher'>({s['teacher']})</div>")
                
                if not cell_items: cell = "-"
                else: cell = "<hr style='margin:2px'>".join(cell_items)
                
                html += f"<td>{cell}</td>"
                if p in BREAKS:
                    if idx == 0: html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
            html += "</tr>"
        html += "</tbody></table></div>"

        # --- 2. SEPARATED TABLES (แยกสาย - ถ้ามีมากกว่า 1 สาย) ---
        if len(programs_list) > 1:
            html += "<h4 style='margin-top:20px; color:#555;'>👇 ตารางแยกตามสายการเรียน:</h4>"
            for prog in programs_list:
                html += f"""<div class="section"><h4>- ห้อง {room} (สาย {prog})</h4>
                    <table><thead><tr><th class="day-col">วัน</th>"""
                for p in range(1, 10):
                    html += f"<th>{p}<br><span style='font-size:0.7em;'>{PERIODS[p]}</span></th>"
                    if p in BREAKS: html += f"<th class='break-col'></th>"
                html += "</tr></thead><tbody>"
                for idx, d in enumerate(DAYS):
                    html += f"<tr><td class='day-col'>{d}</td>"
                    for p in range(1, 10):
                        slots = st.session_state.schedule_data[room][d][p]
                        cell_items = []
                        if slots:
                            for s in slots:
                                if s.get('program', 'รวมทุกสาย') == prog or s.get('program', 'รวมทุกสาย') == 'รวมทุกสาย':
                                    prog_text = s.get('program', 'รวม')
                                    prog_html = f"<span class='prog-badge'>{prog_text}</span>" if prog_text != "รวมทุกสาย" else ""
                                    cell_items.append(f"<div class='subject'>{s['subject']} {prog_html}</div><div class='teacher'>({s['teacher']})</div>")
                        
                        if not cell_items: cell = "-"
                        else: cell = "<hr style='margin:2px'>".join(cell_items)
                        
                        html += f"<td>{cell}</td>"
                        if p in BREAKS:
                            if idx == 0: html += f"<td class='break-col' rowspan='5'>{BREAKS[p]}</td>"
                    html += "</tr>"
                html += "</tbody></table></div>"
        
        html += "<div class='page-break'></div>"
            
    html += "</body></html>"
    return html

# --- 6. เมนูหลัก ---
menu = st.sidebar.radio("เมนูหลัก", [
    "1. 🗓️ ตารางเรียนรวม (Master View)",
    "2. 📅 จัดตารางสอน", 
    "3. 👥 ข้อมูลของครู", 
    "4. 🏫 ข้อมูลห้องเรียน", 
    "5. 🖨️ ระบบรายงาน",
    "6. 📊 Dashboard สรุปยอด"
])

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

# === MENU 2 ===
elif menu == "2. 📅 จัดตารางสอน":
    st.header("จัดตารางสอน (Auto-Save 💾)")
    current_rooms_list = get_all_rooms()
    
    if not current_rooms_list:
        st.warning("⚠️ ยังไม่มีข้อมูลห้องเรียน กรุณาไปเพิ่มที่เมนู 'ข้อมูลห้องเรียน' ก่อนครับ")
    else:
        selected_grade = st.selectbox("เลือกห้องเรียน:", current_rooms_list)
        program_str = get_room_program(selected_grade)
        programs_list = [p.strip() for p in str(program_str).split(",") if p.strip()]
        st.caption(f"🎓 สายการเรียน: **{program_str}**")
        st.markdown("---")

        # --- 1. บันทึกตารางสอน ---
        st.subheader("📝 บันทึกตารางสอน")
        
        c_day, c_prog = st.columns(2)
        with c_day:
            edit_day = st.selectbox("1. เลือกวันที่จะแก้ไข:", DAYS)
        with c_prog:
            target_prog_for_edit = "รวมทุกสาย"
            if len(programs_list) > 1:
                target_prog_for_edit = st.selectbox("2. เลือกสายการเรียน:", ["รวมทุกสาย"] + programs_list)
            else:
                st.selectbox("2. สายการเรียน:", ["รวมทุกสาย"], disabled=True)

        with st.form(key="daily_editor_form"):
            st.info(f"💡 ระบบแสดงเฉพาะครูที่ **ว่าง** และ **สอนห้อง {selected_grade}** เท่านั้น")
            st.markdown(f"#### 📅 วัน{edit_day} ({target_prog_for_edit})")
            
            new_schedule_data = {} 
            cols = st.columns(3)
            
            for p in range(1, 10):
                col_idx = (p - 1) % 3
                with cols[col_idx]:
                    current_slots = st.session_state.schedule_data[selected_grade][edit_day][p]
                    current_teacher = None
                    for s in current_slots:
                        if s.get('program', 'รวมทุกสาย') == target_prog_for_edit or target_prog_for_edit == "รวมทุกสาย":
                            current_teacher = s['teacher']
                            break
                    
                    avail_teachers, busy_teachers = get_available_teachers(selected_grade, edit_day, p)
                    options = ["-- ว่าง --"] + avail_teachers
                    if current_teacher and current_teacher not in options:
                        options.append(current_teacher) 
                    
                    idx = 0
                    if current_teacher in options:
                        idx = options.index(current_teacher)
                        
                    selected = st.selectbox(
                        f"คาบ {p} ({PERIODS[p]})",
                        options=options,
                        index=idx,
                        key=f"sel_{p}"
                    )
                    new_schedule_data[p] = selected

            st.markdown("---")
            submit_btn = st.form_submit_button("💾 บันทึกตารางวันนี้", type="primary", use_container_width=True)
            
            if submit_btn:
                updates_map = {}
                for p, t in new_schedule_data.items():
                    if t != "-- ว่าง --":
                        updates_map[p] = t
                
                conflicts = validate_marathon_teaching(updates_map, selected_grade, edit_day)
                
                if conflicts:
                    st.session_state.marathon_confirm_data = {
                        'grade': selected_grade,
                        'day': edit_day,
                        'new_data': new_schedule_data,
                        'target_prog': target_prog_for_edit,
                        'conflicts': conflicts
                    }
                    st.rerun()
                else:
                    apply_schedule_updates(selected_grade, edit_day, new_schedule_data, target_prog_for_edit)
                    st.success(f"✅ บันทึกตารางวัน{edit_day} เรียบร้อยแล้ว")
                    time.sleep(1)
                    st.rerun()

        # ส่วนยืนยันมาราธอน
        if st.session_state.marathon_confirm_data:
            data = st.session_state.marathon_confirm_data
            st.warning("⚠️ **แจ้งเตือน: พบการสอนมาราธอน**")
            for c in data['conflicts']:
                st.error(c)
            st.info("คุณต้องการยืนยันการบันทึกหรือไม่? (กด 'ยืนยัน' เพื่อบันทึกแม้จะมีข้อแจ้งเตือน)")
            
            col_conf1, col_conf2 = st.columns([0.2, 0.8])
            if col_conf1.button("✅ ยืนยันการบันทึก", type="primary"):
                apply_schedule_updates(data['grade'], data['day'], data['new_data'], data['target_prog'])
                st.session_state.marathon_confirm_data = None
                st.success("บันทึกข้อมูลเรียบร้อย (แบบมาราธอน)")
                time.sleep(1)
                st.rerun()
            if col_conf2.button("❌ ยกเลิก"):
                st.session_state.marathon_confirm_data = None
                st.rerun()

        st.markdown("---")

        # --- 2. ส่วนตารางเรียน (View) ---
        c_head, c_reset = st.columns([0.8, 0.2])
        with c_head:
            st.subheader(f"👀 ตารางเรียนปัจจุบัน: {selected_grade}")
        with c_reset:
            with st.expander("🗑️ ล้างข้อมูลทั้งหมด", expanded=False):
                if st.button("ยืนยัน", type="primary", key="btn_reset_confirm"):
                    for d in DAYS:
                        for p in range(1, 10):
                            st.session_state.schedule_data[selected_grade][d][p] = []
                    save_data_to_gsheets()
                    st.success("ล้างข้อมูลเรียบร้อย")
                    time.sleep(1)
                    st.rerun()

        html_table = render_beautiful_table(selected_grade, st.session_state.schedule_data)
        st.markdown(html_table, unsafe_allow_html=True)
        
        if len(programs_list) > 1:
            st.markdown("---")
            st.write("### 📂 ตารางแยกตามสายการเรียน")
            for prog in programs_list:
                st.write("")
                st.subheader(f"🔷 สาย: {prog}")
                st.markdown(render_beautiful_table(selected_grade, st.session_state.schedule_data, filter_program=prog), unsafe_allow_html=True)

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
                save_data_to_gsheets()
                st.rerun()
    if selected_option != "-- เพิ่มครูคนใหม่ --":
        if st.button("🗑️ ลบครูท่านนี้", type="secondary"):
             st.session_state.teachers_data = st.session_state.teachers_data[st.session_state.teachers_data["ชื่อ-สกุล"] != selected_option]
             save_data_to_gsheets()
             st.success("ลบเรียบร้อย"); st.rerun()

    st.markdown("---")
    st.subheader("📋 รายชื่อครูในระบบ")
    st.dataframe(st.session_state.teachers_data, use_container_width=True)

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
                save_data_to_gsheets()
                st.rerun()
    if selected_room_opt != "-- เพิ่มห้องใหม่ --":
        if st.button("🗑️ ลบห้องเรียนนี้", type="secondary"):
             st.session_state.classrooms_data = st.session_state.classrooms_data[st.session_state.classrooms_data["ห้องเรียน"] != selected_room_opt]
             save_data_to_gsheets()
             st.success("ลบเรียบร้อย"); st.rerun()

    st.markdown("---")
    st.subheader("📋 รายชื่อห้องเรียนในระบบ")
    st.dataframe(st.session_state.classrooms_data, use_container_width=True)

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
        st.subheader("รายงานตารางเรียนรายระดับชั้น (แยกตามสายการเรียน)")
        col_g1, col_g2 = st.columns([1, 2])
        with col_g1: sel_level = st.text_input("ค้นหาระดับชั้น (เช่น ป.4)", value="ป.4")
        with col_g2:
            st.write(""); st.write("")
            if sel_level:
                # [UPDATED] ใช้ฟังก์ชันใหม่ที่สร้างตารางแยกสาย
                html_report_grade = generate_grade_report_html(sel_level)
                st.download_button(f"📥 ดาวน์โหลด Report แยกสายการเรียน ({sel_level})", data=html_report_grade, file_name=f"grade_{sel_level}_report.html", mime="text/html", type="primary")
        
        if sel_level:
            st.markdown("---")
            st.write(f"**ตัวอย่างห้องที่พบ:**")
            found_rooms = [r for r in get_all_rooms() if sel_level in r]
            if found_rooms:
                example_room = found_rooms[0]
                program_str = get_room_program(example_room)
                programs_list = [p.strip() for p in str(program_str).split(",") if p.strip()]
                if not programs_list: programs_list = ["รวมทุกสาย"]
                
                st.markdown(f"**ห้อง: {example_room}**")
                for prog in programs_list:
                    st.write(f"🔹 **สาย: {prog}**")
                    st.markdown(render_beautiful_table(example_room, st.session_state.schedule_data, filter_program=prog), unsafe_allow_html=True)
            else:
                st.warning("ไม่พบห้องเรียนที่ค้นหา")

elif menu == "6. 📊 Dashboard สรุปยอด":
    st.header("Dashboard สรุปภาระงานสอน")
    all_rooms_list = get_all_rooms()
    unique_levels = sorted(list(set([r.split('/')[0] for r in all_rooms_list if '/' in r])))
    filter_options = ["ภาพรวมทั้งโรงเรียน"] + unique_levels
    selected_filter = st.selectbox("🔍 เลือกดูข้อมูลเฉพาะระดับชั้น:", filter_options)
    
    teacher_stats = {}
    all_teachers = st.session_state.teachers_data["ชื่อ-สกุล"].tolist()
    for t in all_teachers:
        teacher_stats[t] = { "count": 0, "rooms": set(), "programs": set() }
    
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
                    prog = s.get('program', 'รวม')
                    if t_name in teacher_stats:
                        teacher_stats[t_name]["count"] += 1
                        teacher_stats[t_name]["rooms"].add(room)
                        teacher_stats[t_name]["programs"].add(prog)
                    else:
                        teacher_stats[t_name] = { "count": 1, "rooms": {room}, "programs": {prog} }
                    total_slots += 1

    active_teachers_count = sum(1 for t in teacher_stats if teacher_stats[t]["count"] > 0)
    c1, c2, c3 = st.columns(3)
    c1.metric("จำนวนครู (ที่มีสอน)", f"{active_teachers_count} คน")
    c2.metric(f"ยอดสอนรวม ({selected_filter})", f"{total_slots} คาบ")
    
    st.markdown("---")
    
    data_list = []
    for t_name, stats in teacher_stats.items():
        if stats["count"] >= 0:
            sorted_rooms = sorted(list(stats["rooms"]), key=natural_sort_key)
            sorted_progs = sorted(list(stats["programs"]))
            data_list.append({
                "ชื่อครู": t_name,
                "จำนวนคาบ/สัปดาห์": stats["count"],
                "ห้องที่สอน": ", ".join(sorted_rooms),
                "สายการเรียน": ", ".join(sorted_progs)
            })
            
    if data_list:
        df_stats = pd.DataFrame(data_list)
        df_stats = df_stats.sort_values(by="จำนวนคาบ/สัปดาห์", ascending=False).reset_index(drop=True)
        
        st.subheader(f"📊 กราฟแสดงจำนวนคาบสอน ({selected_filter})")
        st.bar_chart(df_stats.set_index("ชื่อครู")["จำนวนคาบ/สัปดาห์"])
        
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
                ),
                "ห้องที่สอน": st.column_config.TextColumn("ห้องที่สอน", width="medium"),
                "สายการเรียน": st.column_config.TextColumn("สายการเรียน", width="small")
            },
            use_container_width=True
        )
    else:
        st.warning("ไม่พบข้อมูลการสอนในระดับชั้นที่เลือก")
