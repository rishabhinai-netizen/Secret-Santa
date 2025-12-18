import streamlit as st
from supabase import create_client, Client
import random
import time
from datetime import datetime, timezone
import pandas as pd

# --- 1. SETUP & SECRETS ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except:
    st.error("Secrets not found. Please set SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

supabase: Client = create_client(url, key)

st.set_page_config(page_title="Team Secret Santa", page_icon="🎅", layout="centered")

# --- 2. HIDE STREAMLIT UI (STEALTH MODE) ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stToolbar"] {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
def get_config(key):
    response = supabase.table('config').select('value').eq('key', key).execute()
    if response.data:
        return response.data[0]['value']
    return None

def set_config(key, value):
    supabase.table('config').update({'value': value}).eq('key', key).execute()

def login(email, phrase):
    res = supabase.table('participants').select('*').eq('email', email).eq('passphrase', phrase).execute()
    return res.data[0] if res.data else None

def get_assignment(santa_email):
    res = supabase.table('assignments').select('*').eq('santa_email', santa_email).execute()
    return res.data[0] if res.data else None

def get_user_by_email(email):
    res = supabase.table('participants').select('*').eq('email', email).execute()
    return res.data[0] if res.data else None

def get_all_participants_names():
    res = supabase.table('participants').select('name, email').eq('is_admin', False).execute()
    return res.data

def run_assignment():
    users = supabase.table('participants').select('email').eq('is_admin', False).execute()
    emails = [u['email'] for u in users.data]
    
    if len(emails) < 2:
        st.error(f"Need at least 2 participants (found {len(emails)}). Admin is excluded.")
        return

    santas = emails.copy()
    recipients = emails.copy()
    
    attempts = 0
    while True:
        random.shuffle(recipients)
        if all(s != r for s, r in zip(santas, recipients)):
            break
        attempts += 1
        if attempts > 100:
            st.error("Could not generate valid pairs. Try again.")
            return

    data = []
    for s, r in zip(santas, recipients):
        data.append({'santa_email': s, 'recipient_email': r})
    
    try:
        supabase.table('assignments').delete().neq('status', 'impossible').execute()
    except:
        pass 
    
    supabase.table('assignments').insert(data).execute()
    set_config('stage', 'clue_1')
    st.success(f"Assignments generated for {len(emails)} people!")

# --- 4. MAIN UI LOGIC ---
st.title("🎄 Team Secret Santa")

if 'user' not in st.session_state:
    st.session_state.user = None

# A. LOGIN / SIGNUP SCREEN
if not st.session_state.user:
    tab1, tab2 = st.tabs(["Login", "Signup"])
    
    with tab1:
        email = st.text_input("Email", key="login_email").lower().strip()
        phrase = st.text_input("Passphrase", type="password", key="login_pass")
        if st.button("Log In"):
            user = login(email, phrase)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid email or passphrase")

    with tab2:
        st.caption("Admin account is strictly for management.")
        new_name = st.text_input("Full Name")
        new_email = st.text_input("Email", key="signup_email").lower().strip()
        new_phrase = st.text_input("Create Passphrase", type="password")
        
        st.write("---")
        st.write("📝 **Tell us about yourself (Your Santa will see this):**")
        
        # CLUE 1
        st.write("**Clue 1 — My Non-Negotiable Daily Habit**")
        st.caption("One thing I do almost every day that I genuinely miss if it doesn’t happen. (e.g., A quiet walk with my earphones, Writing a to-do list by hand, Gym or some movement, My morning coffee before I speak to anyone)")
        c1 = st.text_input("Answer for Clue 1", placeholder="Your daily habit...")

        # CLUE 2
        st.write("**Clue 2 — Something Small That Instantly Lifts My Mood**")
        st.caption("A simple thing that makes an ordinary day feel better. (e.g., A handwritten note, A clean desk setup, Funny Chitchat, Appreciation from my Boss)")
        c2 = st.text_input("Answer for Clue 2", placeholder="Your mood lifter...")

        # CLUE 3
        st.write("**Clue 3 — One Thing I’d Never Buy for Myself (But Would Love to Receive)**")
        st.caption("Something I enjoy but usually don’t spend money on. (e.g., A premium notebook, A desk plant, Laughing Buddha, Headphone)")
        c3 = st.text_input("Answer for Clue 3", placeholder="Your wish...")
        
        consent = st.checkbox("I promise to play nicely.")
        
        if st.button("Join"):
            if consent and new_email and c1 and c2 and c3:
                try:
                    supabase.table('participants').insert({
                        'email': new_email, 'name': new_name, 'passphrase': new_phrase,
                        'clue_1': c1, 'clue_2': c2, 'clue_3': c3
                    }).execute()
                    st.success("Signed up! Please Log In.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please fill all clues and fields!")

else:
    # B. LOGGED IN DASHBOARD
    user = st.session_state.user
    
    # GLOBAL BANNER FOR EVENT DETAILS
    st.info("📅 **Game Event:** 23rd December 2025 | ⏰ **5:00 PM** | 📍 **M8 Meeting Room**")
    
    st.write(f"Hello, **{user['name']}**!")
    
    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()
        
    stage = get_config('stage')
    
    # --- ADMIN VIEW ---
    if user['is_admin']:
        st.divider()
        st.subheader("🛡️ Admin Cockpit")
        st.write(f"**Current Stage:** `{stage}`")
        
        col1, col2 = st.columns(2)
        with col1:
            # SAFETY LOCK: Only show Generate button if in Signup stage
            if stage == 'signup':
                if st.button("Generate Assignments (Exclude Me)"):
                    run_assignment()
            else:
                st.warning("Assignments Locked. (Stage is not 'signup')")
                st.caption("To regenerate, set stage back to 'signup' first.")
            
            st.write("---")
            new_stage = st.selectbox("Set Stage", 
                ['signup', 'clue_1', 'clue_2', 'clue_3', 'name_reveal', 'event_day', 'grand_reveal'])
            if st.button("Update Stage"):
                set_config('stage', new_stage)
                st.rerun()
                
            if stage in ['event_day', 'grand_reveal']:
                 st.write("---")
                 if st.button("🚀 TRIGGER FINAL REVEAL"):
                     set_config('stage', 'grand_reveal')
                     st.rerun()

        with col2:
             st.write("**Participant Status**")
             all_users = supabase.table('participants').select('email, name').eq('is_admin', False).execute().data
             all_assigns = supabase.table('assignments').select('*').execute().data
             
             status_data = []
             for u in all_users:
                 assign = next((a for a in all_assigns if a['recipient_email'] == u['email']), None)
                 status = "Not Assigned"
                 santa_clue = "❌"
                 gift_status = "Waiting"
                 guess_made = "No"
                 
                 if assign:
                     their_santa_row = next((a for a in all_assigns if a['santa_email'] == u['email']), None)
                     if their_santa_row and their_santa_row.get('santa_clue_1'):
                         santa_clue = "✅"
                     
                     status = assign['status']
                     if assign['status'] == 'received': gift_status = "Received 📦"
                     if assign['status'] in ['opened', 'revealed']: gift_status = "Opened 🎁"
                     
                     if assign.get('guess_count', 0) > 0:
                         guess_made = "Yes"
                 
                 status_data.append({
                     "Name": u['name'],
                     "Santa Clue?": santa_clue,
                     "Gift": gift_status,
                     "Guessed?": guess_made
                 })
             
             df = pd.DataFrame(status_data)
             st.dataframe(df, hide_index=True)

    st.divider()

    # --- PARTICIPANT VIEW ---
    if not user['is_admin']:
        
        # 1. WAITING ROOM (LOBBY)
        if stage == 'signup':
            st.subheader("☕ The Waiting Room")
            st.warning("All the users have not signed up yet!. Please wait")
            
            st.write("### Who is already here?")
            participants = supabase.table('participants').select('name').eq('is_admin', False).execute().data
            for p in participants:
                st.write(f"- {p['name']}")
            st.caption("Refresh this page occasionally to check if the game has started.")
            st.stop()

        # 2. GAME STARTED
        assignment = get_assignment(user['email'])
        if not assignment:
            st.error("The game has started, but you don't have a Santa Assignment.")
            st.write("Possible reasons: Signed up late or using Admin account.")
            st.stop()
            
        target = get_user_by_email(assignment['recipient_email'])
        
        # --- TABS ---
        tab_santa, tab_recipient, tab_leaderboard, tab_help = st.tabs(["🎅 My Mission", "🎁 My Gift", "🏆 Leaderboard", "❓ How to Play"])

        # --- TAB 1: SANTA MISSION ---
        with tab_santa:
            if stage in ['name_reveal', 'event_day', 'grand_reveal']:
                st.success(f"You are the Secret Santa for **{target['name']}**! Excited? 🤩")
            else:
                st.write("🕵️ **Target Identity: HIDDEN**")

            st.caption("Clues provided by your target:")
            if stage != 'signup': st.info(f"1. Daily Habit: {target['clue_1']}")
            if stage not in ['signup', 'clue_1']: st.info(f"2. Mood Lifter: {target['clue_2']}")
            if stage == 'clue_3' or stage in ['name_reveal', 'event_day', 'grand_reveal']: st.info(f"3. Wishlist: {target['clue_3']}")
            
            st.divider()
            st.write("🕵️ **Provide 1 Clue About YOURSELF**")
            st.caption("Your target will see this after they open the gift to guess who you are.")
            
            sc1 = st.text_input("Your Clue", value=assignment.get('santa_clue_1') or "")
            
            if st.button("Save My Identity Clue"):
                supabase.table('assignments').update({
                    'santa_clue_1': sc1
                }).eq('santa_email', user['email']).execute()
                st.toast("Clue Saved!")

        # --- TAB 2: RECIPIENT BOX ---
        with tab_recipient:
            my_row = supabase.table('assignments').select('*').eq('recipient_email', user['email']).execute().data[0]
            status = my_row['status']
            guesses_used = my_row.get('guess_count', 0)
            
            if stage == 'event_day' or stage == 'grand_reveal':
                if status == 'assigned':
                    st.button("📦 I have RECEIVED my gift", 
                              on_click=lambda: supabase.table('assignments').update({'status': 'received'}).eq('recipient_email', user['email']).execute())
                
                elif status == 'received':
                    st.success("You have the gift!")
                    if st.button("🎁 I have OPENED my gift"):
                         supabase.table('assignments').update({'status': 'opened'}).eq('recipient_email', user['email']).execute()
                         st.rerun()

                elif status in ['opened', 'revealed']:
                    st.success("Gift Opened! Now... Who sent it?")
                    
                    st.write("#### 🕵️ Clue from your Santa:")
                    if my_row['santa_clue_1']: 
                        st.info(f"\"{my_row['santa_clue_1']}\"")
                    else: 
                        st.warning("(Santa left no clue!)")
                    
                    st.write("---")
                    
                    if not my_row.get('is_correct_guess') and guesses_used < 2:
                        st.write("#### ⚡ Fastest Finger First!")
                        
                        if guesses_used == 0:
                            st.caption("You have **2 Chances**. Make them count!")
                        elif guesses_used == 1:
                            st.warning("⚠️ LAST CHANCE! Think carefully.")
                            st.error(f"Your previous guess ({my_row.get('first_wrong_guess')}) was wrong.")

                        people = get_all_participants_names()
                        options = {
                            p['name']: p['email'] 
                            for p in people 
                            if p['email'] != user['email'] 
                            and p['email'] != my_row.get('first_wrong_guess')
                        }
                        
                        guess_name = st.selectbox("Who is your Santa?", ["Select..."] + list(options.keys()))
                        
                        if st.button("🔒 Lock In Guess"):
                            if guess_name != "Select...":
                                guessed_email = options[guess_name]
                                is_correct = (guessed_email == my_row['santa_email'])
                                
                                update_data = {
                                    'guess_count': guesses_used + 1,
                                    'guess_timestamp': datetime.now(timezone.utc).isoformat()
                                }
                                
                                if is_correct:
                                    update_data['is_correct_guess'] = True
                                    update_data['guess_email'] = guessed_email
                                else:
                                    if guesses_used == 0:
                                        update_data['first_wrong_guess'] = guessed_email
                                
                                supabase.table('assignments').update(update_data).eq('recipient_email', user['email']).execute()
                                st.rerun()
                                
                    elif my_row.get('is_correct_guess'):
                         st.success("✅ CORRECT! You nailed it.")
                         st.caption("Check the leaderboard to see if you were fast enough!")
                         
                         if stage == 'grand_reveal':
                            santa_info = get_user_by_email(my_row['santa_email'])
                            st.balloons()
                            st.markdown(f"### Your Santa was: **{santa_info['name']}**")
                            
                    else:
                        st.error("❌ Out of guesses!")
                        st.write("Wait for the Grand Reveal to see who it was.")
                        
                        if stage == 'grand_reveal':
                            santa_info = get_user_by_email(my_row['santa_email'])
                            st.balloons()
                            st.markdown(f"### Your Santa was: **{santa_info['name']}**")


        # --- TAB 3: LEADERBOARD ---
        with tab_leaderboard:
            st.subheader("🏆 Speed Guessing Leaderboard")
            st.caption("Top 5 Fastest Correct Guesses get a prize!")
            
            response = supabase.table('assignments').select('recipient_email, guess_timestamp, is_correct_guess').execute()
            
            if not response.data:
                 st.write("No guesses yet...")
            else:
                 guessed_only = [d for d in response.data if d['guess_timestamp'] is not None]
                 correct_guesses = [d for d in guessed_only if d['is_correct_guess']]
                 correct_guesses.sort(key=lambda x: x['guess_timestamp'])
                 
                 if not correct_guesses:
                     st.write("No correct guesses yet...")
                 else:
                     for idx, entry in enumerate(correct_guesses):
                         user_info = get_user_by_email(entry['recipient_email'])
                         if user_info:
                             rank = idx + 1
                             medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                             if rank > 5: medal = "❌"
                             
                             st.write(f"### {medal} {user_info['name']}")
                             if rank == 5:
                                 st.divider()
                                 st.caption("--- PRIZE CUTOFF (Top 5 Only) ---")

        # --- TAB 4: SOP / HELP MANUAL ---
        with tab_help:
            st.header("📖 How to Play")
            st.info("👋 **Welcome to the Team Secret Santa!**\n\nYour goal: Give a great gift, keep your identity secret, and guess who your Santa is!")
            st.subheader("1️⃣ Before the Event")
            st.markdown("""
            * **Check 'My Mission':** See who your target is and read their clues.
            * **Leave a Clue:** In the 'My Mission' tab, write ONE clue about yourself. This is the **only** hint your target will get!
            * **Buy the Gift:** Bring it to the event wrapped and labeled.
            """)
            st.subheader("2️⃣ On Event Day")
            st.markdown("""
            * **Step A:** When you hold the physical gift box, click **'📦 I have RECEIVED'**.
            * **Step B:** Unwrap the gift! Then click **'🎁 I have OPENED'**.
            * **Step C:** The app will reveal **Santa's Clue** to you.
            """)
            st.subheader("3️⃣ The Speed Game")
            st.warning("⚡ **This is a race!**")
            st.markdown("""
            * Once you see the clue, guess who your Santa is immediately.
            * **Top 5 Fastest Correct Guessers** win an extra prize!
            * You have **2 Chances**.
                * Guess 1 Wrong? You get one more try.
                * Guess 2 Wrong? You are out!
            """)
            st.subheader("4️⃣ The Grand Reveal")
            st.success("🎉 Once everyone has guessed, the Admin will press the big red button and all identities will be revealed!")
