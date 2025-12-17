import streamlit as st
import os
import json
from dotenv import load_dotenv
from fpdf import FPDF
import plotly.express as px
import pandas as pd
from groq import Groq
import base64
import hashlib
import math
import re
import sys


# ---- FULL WIDTH / WIREFRAME CSS ----
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .main .block-container {
        max-width: 100vw !important;
        padding-top: 0.2rem;
        padding-left: 0rem;
        padding-right: 0rem;
    }
    .profile-circle {
        border: 2.5px solid #111;
        background: #f7fafc;
        border-radius: 50%;
        width: 100px;
        height: 100px;
        display:flex; align-items:center;justify-content:center;
        font-size:1.3rem;
        font-weight:600;
        margin: 20px auto 16px auto;
    }
    </style>
""", unsafe_allow_html=True)


# Optional background image as before
if os.path.exists("career coach.png"):
    with open("career coach.png", "rb") as img_file:
        img_bytes = img_file.read()
    img_base64 = base64.b64encode(img_bytes).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{img_base64}");
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-position: center;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key)


USER_DB_FILE = "users_db.json"


def load_users():
    if not os.path.exists(USER_DB_FILE):
        return {}
    with open(USER_DB_FILE, "r") as f:
        return json.load(f)
def save_users(users):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f, indent=2)
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
def authenticate_user(username, password):
    users = load_users()
    if username in users:
        hashed = hash_password(password)
        if users[username]["password"] == hashed:
            return True
    return False
def register_user(username, password, profile=None):
    users = load_users()
    if username in users:
        return False
    users[username] = {"password": hash_password(password), "profile": profile or {}}
    save_users(users)
    return True
def save_user_profile(username, profile_data):
    users = load_users()
    if username in users:
        users[username]["profile"] = profile_data
        save_users(users)
def load_user_profile(username):
    users = load_users()
    if username in users:
        return users[username].get("profile", {})
    return {}


tab_names = [
    "Profile Analyzer",
    "Skill & Resource Recommender",
    "Learning Roadmap",
    "Assessment",
    "Progress Tracker & Dashboard"
]


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "selected_tab" not in st.session_state:
    st.session_state.selected_tab = 0


def login_ui():
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Username", key="login_username")
    password = st.sidebar.text_input("Password", type="password", key="login_password")
    if st.sidebar.button("Login"):
        if authenticate_user(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.sidebar.success(f"Logged in as {username}")
            profile = load_user_profile(username)
            st.session_state.loaded_profile = profile
            st.session_state.skills_list = profile.get('skills_list', '')
            st.session_state.roadmap_text = profile.get('roadmap_text', '')
            st.rerun()   # single-click login: rerun after setting state [web:12]
        else:
            st.sidebar.error("Invalid username or password")
def signup_ui():
    st.sidebar.header("Sign Up")
    new_username = st.sidebar.text_input("Choose Username", key="signup_username")
    new_password = st.sidebar.text_input("Choose Password", type="password", key="signup_password")
    if st.sidebar.button("Sign Up"):
        if new_username and new_password:
            if register_user(new_username, new_password):
                st.sidebar.success(f"User {new_username} registered! Please log in.")
            else:
                st.sidebar.error("Username already exists")
        else:
            st.sidebar.error("Provide username and password")


def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.loaded_profile = {}
    st.session_state.skills_list = ''
    st.session_state.roadmap_text = ''


# Start layout with sidebar
with st.sidebar:
    if st.session_state.logged_in:
        # Profile circle icon
        st.markdown(f'<div class="profile-circle">{st.session_state.username[:2].upper()}</div>', unsafe_allow_html=True)
        # Navigation tabs, vertical order
        selected = st.radio("Navigation", tab_names, index=st.session_state.selected_tab, key="sidebar_nav")
        st.session_state.selected_tab = tab_names.index(selected)
        st.markdown("---")
        if st.button("Logout"):
            logout()
            st.rerun()
    else:
        # Profile circle placeholder
        st.markdown('<div class="profile-circle">?</div>', unsafe_allow_html=True)
        login_ui()
        st.markdown("---")
        signup_ui()


# ---- MAIN CONTENT AREA ----
if st.session_state.logged_in:
    st.markdown('<div style="max-width:100vw;padding:40px 0 0 0;">', unsafe_allow_html=True)
    st.markdown('<h1 style="text-align:center;">AI Career Coach</h1>', unsafe_allow_html=True)
    # Load existing profile data
    loaded = st.session_state.get("loaded_profile", {})
    role = st.text_input("Your current role", value=loaded.get("role", ""), key="main_role")
    skills = st.text_area("Your current skills (comma separated)", value=loaded.get("skills", ""), key="main_skills")
    goal = st.text_input("Your career goal", value=loaded.get("goal", ""), key="main_goal")


    for key in ["profile_analysis", "skills_list", "roadmap_text", "assessment_scores",
            "mastered_skills", "roadmap_skills", "assessment_questions", "current_week_index"]:
        if key not in st.session_state:
            if key == "current_week_index":
                st.session_state[key] = 0
            else:
                st.session_state[key] = "" if key not in (
                    "assessment_scores", "mastered_skills", "roadmap_skills", "assessment_questions") else ({} if key == "assessment_scores" else [])


    def analyze_profile(role, skills, goal):
        prompt = (
            f"Analyze the following professional profile:\nCurrent Role: {role}\nCurrent Skills: {skills}\nCareer Goal: {goal}\n\n"
            "Provide a detailed analysis including strengths, skill gaps, and suggestions."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    def recommend_skills_plus(role, skills, goal):
        prompt = (
            f"Profile:\nRole:{role}\nSkills:{skills}\nGoal:{goal}\n"
            "List top 5 skills user should learn (each on a new line), with:\n"
            "Skill name | Brief description | Top verified resource name | Resource link\n"
            "Example:\nMachine Learning | Fundamentals of ML algorithms | Coursera ML course | https://coursera.org/ml\n"
            "Give real, reputable resources."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    def get_roadmap(role, skills, goal, roadmap_skills=None):
        extra_skill_info = ""
        if roadmap_skills:
            extra_skill_info = f"\nSkills chosen for roadmap: {', '.join(roadmap_skills)}"
        prompt = (
            f"Profile:\nRole: {role}\nSkills: {skills}\nGoal: {goal}\n"
            f"{extra_skill_info}\n"
            "Generate a week-by-week learning roadmap (plain text) to help the user achieve their goal."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    def parse_roadmap(roadmap_text):
        roadmap = []
        for line in roadmap_text.split('\n'):
            if line.strip().lower().startswith("week"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    week = parts[0].strip()
                    task = parts[1].strip()
                    roadmap.append((week, task))
        return roadmap
    def suggest_job_profiles(goal, skills, roadmap_skills=None):
        skillset = ', '.join(roadmap_skills) if roadmap_skills else ''
        prompt = f"""Suggest 3-5 concrete job profiles a user can apply for after completing the following career learning plan.
User goal: {goal}
User skills: {skills}
Skills planned: {skillset}
For each, give:
- Role title
- 1-line description matching skillset and goal
Respond as a markdown unordered list.
Avoid duplicates. Do not repeat the user's own goal unless it's a stepping-stone variant.
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()


    i = st.session_state.selected_tab
    if i == 0:
        st.header("Profile Analyzer")
        def save_profile():
            profile = load_user_profile(st.session_state.username)
            profile_data = {"role": role, "skills": skills, "goal": goal}
            profile.update(profile_data)
            if 'skills_list' in profile:
                del profile['skills_list']
            if 'roadmap_text' in profile:
                del profile['roadmap_text']
            save_user_profile(st.session_state.username, profile)
            st.session_state.loaded_profile = profile
            st.session_state.skills_list = ''
            st.session_state.roadmap_text = ''
            st.success("Profile saved successfully!")
        st.button("Save Profile", on_click=save_profile)
        if st.button("Analyze Profile"):
            if not role or not goal:
                st.error("Please enter both your current role and career goal.")
            else:
                with st.spinner("Analyzing profile..."):
                    st.session_state.profile_analysis = analyze_profile(role, skills, goal)
                    st.text_area("Profile Analysis", value=st.session_state.profile_analysis, height=250)
    elif i == 1:
        st.header("Skill & Resource Recommender")
        if st.button("Recommend Skills (detailed)"):
            if not role or not goal:
                st.error("Please enter both your current role and career goal.")
            else:
                with st.spinner("Recommending skills..."):
                    skills_text = recommend_skills_plus(role, skills, goal)
                    st.session_state.skills_list = skills_text
                    profile = load_user_profile(st.session_state.username)
                    profile['skills_list'] = skills_text
                    save_user_profile(st.session_state.username, profile)
                    rows = []
                    for line in skills_text.split('\n'):
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) == 4:
                            skill, desc, res_name, res_link = parts
                            rows.append([skill, desc, res_name, res_link])
                    if rows:
                        df = pd.DataFrame(rows, columns=["Skill", "Description", "Top Resource", "Link"])
                        st.dataframe(df, use_container_width=True)
                        for ix, (skill, desc, res_name, res_link) in enumerate(rows):
                            col1, col2 = st.columns([7, 1])
                            col1.markdown(f"**{skill}**: {desc}\n[{res_name}]({res_link})")
                            if col2.button(f"Add to Roadmap {ix+1}"):
                                if skill not in st.session_state.roadmap_skills:
                                    st.session_state.roadmap_skills.append(skill)
                                    st.success(f"Added {skill} to roadmap!")
                    else:
                        st.info("No structured skills to display.")
        else:
            if st.session_state.skills_list:
                rows = []
                for line in st.session_state.skills_list.split('\n'):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) == 4:
                        skill, desc, res_name, res_link = parts
                        rows.append([skill, desc, res_name, res_link])
                if rows:
                    df = pd.DataFrame(rows, columns=["Skill", "Description", "Top Resource", "Link"])
                    st.dataframe(df, use_container_width=True)
                    for ix, (skill, desc, res_name, res_link) in enumerate(rows):
                        col1, col2 = st.columns([7, 1])
                        col1.markdown(f"**{skill}**: {desc}\n[{res_name}]({res_link})")
                        if col2.button(f"Add to Roadmap {ix+1}"):
                            if skill not in st.session_state.roadmap_skills:
                                st.session_state.roadmap_skills.append(skill)
                                st.success(f"Added {skill} to roadmap!")
    elif i == 2:
        st.header("Learning Roadmap")
        if st.button("Generate Roadmap"):
            if not role or not goal:
                st.error("Please enter both your current role and career goal.")
            else:
                with st.spinner("Generating roadmap ..."):
                    roadmap_text = get_roadmap(role, skills, goal, st.session_state.roadmap_skills)
                    st.session_state.roadmap_text = roadmap_text
                    profile = load_user_profile(st.session_state.username)
                    profile['roadmap_text'] = roadmap_text
                    save_user_profile(st.session_state.username, profile)
                    st.session_state.current_week_index = 0
                    st.subheader("Roadmap (week-wise tasks)")
                    st.text_area("Roadmap", value=roadmap_text, height=300)
                    roadmap_data = [{"Week": week, "Task": task} for week, task in parse_roadmap(roadmap_text)]
                    def export_pdf(roadmap_text):
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font("Arial", size=12)
                        pdf.cell(200, 10, txt="Personalized Learning Roadmap", ln=True, align="C")
                        pdf.ln(10)
                        for line in roadmap_text.split('\n'):
                            pdf.multi_cell(0, 10, txt=line)
                        filename = "roadmap.pdf"
                        pdf.output(filename)
                        return filename
                    pdf_filename = export_pdf(roadmap_text)
                    with open(pdf_filename, "rb") as f:
                        st.download_button(
                            label="Download roadmap as PDF",
                            data=f,
                            file_name=pdf_filename,
                            mime="application/pdf",
                        )
        else:
            if st.session_state.roadmap_text:
                st.subheader("Roadmap (week-wise tasks)")
                st.text_area("Roadmap", value=st.session_state.roadmap_text, height=300)
                roadmap_data = [{"Week": week, "Task": task} for week, task in parse_roadmap(st.session_state.roadmap_text)]
        st.markdown("### Career Aspirations")
        if not role or not goal or not st.session_state.skills_list:
            st.info("Save your profile and generate recommended skills for personalized job suggestions.")
        else:
            with st.spinner("Generating job profile suggestions..."):
                recommended_skills = []
                for line in st.session_state.skills_list.split('\n'):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) == 4:
                        skill, desc, res_name, res_link = parts
                        recommended_skills.append(skill)
                skills_for_aspirations = st.session_state.roadmap_skills if st.session_state.roadmap_skills else recommended_skills
                aspirations_markdown = suggest_job_profiles(goal, skills, skills_for_aspirations)
                st.markdown(aspirations_markdown)
    elif i == 3:
        # ASSESSMENT TAB ONLY
        st.header("Assessment")
        roadmap_tasks = parse_roadmap(st.session_state.get("roadmap_text", ""))
        if not roadmap_tasks:
            st.info("Generate your roadmap first to begin assessments.")
        else:
            current_idx = st.session_state.current_week_index
            if current_idx >= len(roadmap_tasks):
                st.success("Congrats! You completed all weeks.")
            else:
                current_week, current_task = roadmap_tasks[current_idx]
                prev_pass = True
                if current_idx > 0:
                    prev_week = roadmap_tasks[current_idx - 1][0]
                    prev_score = st.session_state.assessment_scores.get(prev_week, 0)
                    if prev_score < 70:
                        st.warning(f"Pass previous week ({prev_week}) assessment to continue.")
                        prev_pass = False
                if prev_pass:
                    if st.button(f"Generate 20 MCQs for {current_week}"):
                        with st.spinner(f"Generating MCQs for {current_week}..."):
                            prompt = f"""For this task generate 20 multiple-choice questions.
Respond as JSON list with objects containing: "question" (str), "options" (list of 4 strings), and "answer" (correct option text).
Task description: {current_task}
"""
                            response = client.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": prompt}]
                            )
                            raw_text = response.choices[0].message.content
                            json_matches = re.findall(r'\[.*\]', raw_text, re.DOTALL)
                            if json_matches:
                                json_str = json_matches[0]
                                try:
                                    questions = json.loads(json_str)
                                except Exception as e:
                                    st.error(f"JSON parsing error: {str(e)}. Try regenerating.")
                                    questions = []
                            else:
                                st.error("No valid JSON found in response. Try regenerating.")
                                questions = []
                            st.session_state.assessment_questions = questions
                            st.session_state.assessment_week = current_week
                            st.success(f"MCQs generated for week {current_week}")
                    if (
                        "assessment_questions" in st.session_state 
                        and st.session_state.assessment_questions 
                        and st.session_state.assessment_week == current_week
                    ):
                        with st.form("assessment_form"):
                            user_answers = {}
                            for ix, q in enumerate(st.session_state.assessment_questions):
                                st.markdown(f"**Q{ix+1}: {q['question']}**")
                                user_answers[ix] = st.radio(
                                    "",
                                    options=q["options"],
                                    key=f"q_{ix}",
                                )
                            submitted = st.form_submit_button("Submit Assessment")
                        if submitted:
                            scores = st.session_state.assessment_scores
                            correct_count = 0
                            for ix, q in enumerate(st.session_state.assessment_questions):
                                ans = user_answers.get(ix, "")
                                correct = (ans == q["answer"])
                                score = 100 if correct else 40
                                week = st.session_state.assessment_week
                                scores[week] = scores.get(week, 0) + score / len(st.session_state.assessment_questions)
                                if correct:
                                    correct_count += 1
                            final_score = int(scores[week])
                            st.session_state.assessment_scores = scores
                            if final_score >= 70:
                                st.success(f"Passed week {current_week} assessment with score {final_score}! ({correct_count}/20 correct)")
                                st.session_state.current_week_index += 1
                                st.session_state.assessment_questions = []
                            else:
                                st.error(f"Failed week {current_week} assessment with score {final_score}. Try again.")
                            for ix, q in enumerate(st.session_state.assessment_questions):
                                st.markdown(f"**Q{ix+1}: {q['question']}**")
                                st.markdown(f"Your answer: {user_answers.get(ix, '')}")
                                st.markdown(f"Correct answer: {q['answer']}")
                                if user_answers.get(ix, "") == q["answer"]:
                                    st.success("Correct")
                                else:
                                    st.error("Incorrect")
    elif i == 4:
        # PROGRESS TRACKER & DASHBOARD TAB ONLY
        st.header("Progress Tracker & Dashboard")
        roadmap_tasks = parse_roadmap(st.session_state.get("roadmap_text", ""))
        assessment_scores = st.session_state.get("assessment_scores", {})
        progress_data = []
        mastered_skills = st.session_state.get("mastered_skills", [])
        passed_weeks = 0
        for week, task in roadmap_tasks:
            score = assessment_scores.get(week, 0)
            status = "Pass" if score >= 70 else "Fail"
            if status == "Pass":
                if week not in mastered_skills:
                    mastered_skills.append(week)
                passed_weeks += 1
            progress_data.append([week, task, score, status])
        st.session_state.mastered_skills = mastered_skills
        total_weeks = len(progress_data)
        percent_complete = math.floor(passed_weeks / total_weeks * 100) if total_weeks else 0
        st.markdown(f"**Progress:** {passed_weeks} / {total_weeks} weeks passed")
        st.progress(percent_complete / 100)
        st.markdown(f"**{percent_complete}% of roadmap passed**")
        df_progress = pd.DataFrame(progress_data, columns=["Week", "Task", "Score", "Status"])
        st.markdown("### Weekly Assessment Summary")
        st.dataframe(df_progress, use_container_width=True)
        st.subheader("Weekly Score Trend")
        scores = [assessment_scores.get(week, 0) for week, _ in roadmap_tasks]
        if scores:
            fig = px.line(x=[week for week, _ in roadmap_tasks], y=scores, markers=True, labels={'x': 'Week', 'y': 'Score'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Assessment scores not available. Complete assessments first.")
        st.subheader("Skills Mastered")
        mastered = [roadmap_tasks[ix][1] for ix, score in enumerate(scores) if score >= 70]
        if mastered:
            st.write(", ".join(mastered))
        else:
            st.write("No skills mastered yet.")
        st.subheader("Upcoming Assessments")
        week_statuses = [(week, score) for (week, _), score in zip(roadmap_tasks, scores)]
        upcoming = [week for week, score in week_statuses if score < 70]
        if upcoming:
            st.write(", ".join(upcoming))
        else:
            st.write("No upcoming assessments. All passed.")


    st.markdown('</div>', unsafe_allow_html=True)
