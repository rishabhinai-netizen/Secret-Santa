import streamlit as st
from supabase import create_client, Client
import random
import time
from datetime import datetime, timezone

# --- SETUP ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except:
    st.error("Secrets not found. Please set SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

supabase: Client = create_client(url, key)

st.set_page_config(page_title="Team Secret Santa", page_icon="🎅")

# --- FUNCTIONS ---
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
    # Helper to get list of names for the dropdown
    res = supabase.table('participants').select('name, email').eq('is_admin', False).execute()
    return res.data

def run_assignment():
    # 1. Fetch only NON-ADMIN participants
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
    
    # Clear old assignments safely
    try:
        supabase.table('assignments').delete().neq('status', 'impossible').execute()
    except:
        pass # Handle table empty case
    
    supabase.table('assignments').insert(data).execute()
    set_config('stage', 'clue_1')
    st.success(f"Assignments generated for {len(emails)} people! (Admin excluded)")

# --- UI ---
st.title("🎄 Team Secret Santa")

if 'user' not in st.session_state:
    st.session_state.user = None

# 1. LOGIN / SIGNUP
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
        st.caption("Admin account is strictly for management. Admins do not participate.")
        new_name = st.text_input("Full Name")
        new_email = st.text_input("Email", key="signup_email").lower().strip()
        new_phrase = st.text_input("Create Passphrase", type="password")
        c1 = st.text_input("Target Clue 1: A hobby")
        c2 = st.text_input("Target Clue 2: A specific like")
        c3 = st.text_input("Target Clue 3: Your vibe")
        consent = st.checkbox("I promise to play nicely.")
        
        if st.button("Join"):
            if consent and new_email:
                try:
                    supabase.table('participants').insert({
                        'email': new_email, 'name': new_name, 'passphrase': new_phrase,
                        'clue_1': c1, 'clue_2': c2, 'clue_3': c3
                    }).execute()
                    st.success("Signed up! Please Log In.")
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    # 2. LOGGED IN VIEW
    user = st.session_state.user
    st.write(f"Hello, **{user['name']}**!")
    
    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()
        
    stage = get_config('stage')
    
    # --- ADMIN PANEL ---
    if user['is_admin']:
        st.divider()
        st.subheader("🛡️ Admin Cockpit")
        st.info(f"Current Stage: {stage}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate Assignments (Exclude Me)"):
                run_assignment()
            
            new_stage = st.selectbox("Set Stage", 
                ['signup', 'clue_1', 'clue_2', 'clue_3', 'name_reveal', 'event_day', 'grand_reveal'])
            if st.button("Update Stage"):
                set_config('stage', new_stage)
                st.rerun()

        with col2:
             # Leaderboard Preview
             st.write("**Assignments Status**")
             cnt = supabase.table('assignments').select('status', count='exact').execute().count
             st.metric("Total Pairs", cnt)

             if stage in ['event_day', 'grand_reveal']:
                 st.write("---")
                 if st.button("🚀 TRIGGER FINAL REVEAL"):
                     set_config('stage', 'grand_reveal')
                     st.rerun()

    st.divider()

    # --- USER DASHBOARD (If not admin) ---
    if not user['is_admin']:
        
        if stage == 'signup':
            st.info("Waiting for everyone to sign up... 🕒")
            st.stop()

        assignment = get_assignment(user['email'])
        if not assignment:
            st.error("You are not in the game (likely signed up late or are Admin).")
            st.stop()
            
        target = get_user_by_email(assignment['recipient_email'])
        
        # TABS for Organized View
        tab_santa, tab_recipient, tab_leaderboard = st.tabs(["🎅 My Mission", "🎁 My Gift", "🏆 Leaderboard"])

        # --- TAB 1: SANTA MISSION ---
        with tab_santa:
            st.subheader(f"Target: {target['name'] if stage in ['name_reveal', 'event_day', 'grand_reveal'] else '???'}")
            
            # Show Target Clues
            st.caption("Clues provided by your target:")
            if stage != 'signup': st.info(f"1. {target['clue_1']}")
            if stage not in ['signup', 'clue_1']: st.info(f"2. {target['clue_2']}")
            if stage == 'clue_3' or stage in ['name_reveal', 'event_day', 'grand_reveal']: st.info(f"3. {target['clue_3']}")
            
            st.divider()
            st.write("🕵️ **Provide Clues About YOURSELF**")
            st.caption("Your target will see these after they open the gift to guess who you are.")
            
            sc1 = st.text_input("Self Clue 1", value=assignment.get('santa_clue_1') or "")
            sc2 = st.text_input("Self Clue 2", value=assignment.get('santa_clue_2') or "")
            sc3 = st.text_input("Self Clue 3", value=assignment.get('santa_clue_3') or "")
            
            if st.button("Save My Identity Clues"):
                supabase.table('assignments').update({
                    'santa_clue_1': sc1, 'santa_clue_2': sc2, 'santa_clue_3': sc3
                }).eq('santa_email', user['email']).execute()
                st.toast("Clues Saved!")

        # --- TAB 2: RECIPIENT BOX ---
        with tab_recipient:
            my_row = supabase.table('assignments').select('*').eq('recipient_email', user['email']).execute().data[0]
            status = my_row['status']
            
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
                    # GAME ON!
                    st.success("Gift Opened! Now... Who sent it?")
                    
                    # 1. Show Santa's Self Clues
                    st.write("#### 🕵️ Clues about your Santa:")
                    if my_row['santa_clue_1']: st.write(f"- {my_row['santa_clue_1']}")
                    else: st.write("- (Santa left no clue 1)")
                    if my_row['santa_clue_2']: st.write(f"- {my_row['santa_clue_2']}")
                    if my_row['santa_clue_3']: st.write(f"- {my_row['santa_clue_3']}")
                    
                    st.write("---")
                    
                    # 2. GUESSING INTERFACE
                    if not my_row['guess_email']:
                        st.write("#### ⚡ Fastest Finger First!")
                        st.caption("Guess correctly and quickly to win an extra prize. You only get ONE guess.")
                        
                        people = get_all_participants_names()
                        # Create dict for dropdown {Name: Email}
                        options = {p['name']: p['email'] for p in people}
                        guess_name = st.selectbox("Who is your Santa?", ["Select..."] + list(options.keys()))
                        
                        if st.button("🔒 Lock In Guess"):
                            if guess_name != "Select...":
                                guessed_email = options[guess_name]
                                is_correct = (guessed_email == my_row['santa_email'])
                                
                                # Record Guess & Time
                                supabase.table('assignments').update({
                                    'guess_email': guessed_email,
                                    'is_correct_guess': is_correct,
                                    'guess_timestamp': datetime.now(timezone.utc).isoformat()
                                }).eq('recipient_email', user['email']).execute()
                                st.rerun()
                    else:
                        st.info("Guess locked in! Check the Leaderboard.")
                        if stage == 'grand_reveal':
                            santa_info = get_user_by_email(my_row['santa_email'])
                            st.balloons()
                            st.markdown(f"### Your Santa was: **{santa_info['name']}**")
                            if my_row['is_correct_guess']:
                                st.success("✅ You guessed CORRECTLY!")
                            else:
                                st.error("❌ Wrong guess.")
                        else:
                            st.write("Wait for the Grand Reveal...")

        # --- TAB 3: LEADERBOARD ---
        with tab_leaderboard:
            st.subheader("🏆 Speed Guessing Leaderboard")
            st.caption("Top 10 Fastest Correct Guesses get a prize!")
            
            # Fetch data logic
            # Get all assignments where guess is correct
            # Sort by timestamp
            
            data = supabase.table('assignments').select('recipient_email, guess_timestamp, is_correct_guess').neq('guess_timestamp', 'null').execute().data
            
            # Filter correct only
            correct_guesses = [d for d in data if d['is_correct_guess']]
            # Sort by time
            correct_guesses.sort(key=lambda x: x['guess_timestamp'])
            
            if not correct_guesses:
                st.write("No correct guesses yet...")
            else:
                for idx, entry in enumerate(correct_guesses):
                    user_info = get_user_by_email(entry['recipient_email'])
                    
                    # Formatting
                    rank = idx + 1
                    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                    if rank > 10: medal = "❌"
                    
                    st.write(f"### {medal} {user_info['name']}")
                    
                    if rank == 10:
                        st.divider()
                        st.caption("--- PRIZE CUTOFF ---")
