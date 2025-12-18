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

def calculate_top_5_speed_winners():
    # Helper to identify who is in the Top 5 (to exclude them from voting)
    response = supabase.table('assignments').select('recipient_email, guess_timestamp, is_correct_guess').execute()
    if not response.data: return []
    
    guessed_only = [d for d in response.data if d['guess_timestamp'] is not None]
    correct_guesses = [d for d in guessed_only if d['is_correct_guess']]
    correct_guesses.sort(key=lambda x: x['guess_timestamp'])
    
    # Return list of emails of top 5 winners
    return [x['recipient_email'] for x in correct_guesses[:5]]

def run_assignment():
    users = supabase.table('participants').select('email').eq('is_admin', False).execute()
    emails = [u['email'] for u in users.data]
    
    if len(emails) < 2:
        st.error(f"Need at least 2 participants. Admin is excluded.")
        return

    santas = emails.copy()
    recipients = emails.copy()
    
    # Generate Unique Tokens (e.g., 101, 102...)
    tokens = random.sample(range(101, 999), len(emails))
    
    attempts = 0
    while True:
        random.shuffle(recipients)
        if all(s != r for s, r in zip(santas, recipients)):
            break
        attempts += 1
        if attempts > 100:
            st.error("Could not generate valid pairs.")
            return

    data = []
    for i, (s, r) in enumerate(zip(santas, recipients)):
        data.append({
            'santa_email': s, 
            'recipient_email': r,
            'recipient_token': str(tokens[i]) # Assign random token to the pair
        })
    
    try:
        supabase.table('assignments').delete().neq('status', 'impossible').execute()
        supabase.table('votes').delete().neq('voter_email', 'impossible').execute() 
    except:
        pass 
    
    supabase.table('assignments').insert(data).execute()
    set_config('stage', 'token_reveal')
    st.success(f"Assignments & Tokens generated for {len(emails)} people!")

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
        st.subheader("🕵️ PART 1: The Clues (For Santa)")
        
        st.write("**Clue 1 — My Non-Negotiable Daily Habit**")
        st.caption("e.g. A quiet walk, Gym, Morning coffee before speaking.")
        c1 = st.text_input("Answer for Clue 1", placeholder="Your daily habit...")

        st.write("**Clue 2 — Something Small That Instantly Lifts My Mood**")
        st.caption("e.g. A handwritten note, A clean desk, Funny Chitchat.")
        c2 = st.text_input("Answer for Clue 2", placeholder="Your mood lifter...")

        st.write("**Clue 3 — One Thing I’d Never Buy for Myself**")
        st.caption("e.g. A premium notebook, A desk plant, Fancy headphones.")
        c3 = st.text_input("Answer for Clue 3", placeholder="Your wish...")
        
        st.write("---")
        st.subheader("🌟 PART 2: The Star Game Questions")
        st.info("These answers will be used for a 2nd game!")
        
        st.write("**Q1. What’s something you secretly enjoy but rarely admit?**")
        sq1 = st.text_input("Secret Enjoyment")
        
        st.write("**Q2. What’s one thing people assume about you that’s usually wrong?**")
        sq2 = st.text_input("Wrong Assumption")
        
        st.write("**Q3. If you disappeared for a weekend, where would we find you?**")
        sq3 = st.text_input("Weekend Hideout")

        consent = st.checkbox("I promise to play nicely.")
        
        if st.button("Join"):
            # --- STRICT VALIDATION START ---
            missing = []
            if not new_email: missing.append("Email")
            if not new_name: missing.append("Name")
            if not new_phrase: missing.append("Passphrase")
            if not c1: missing.append("Clue 1")
            if not c2: missing.append("Clue 2")
            if not c3: missing.append("Clue 3")
            if not sq1: missing.append("Star Question 1")
            if not sq2: missing.append("Star Question 2")
            if not sq3: missing.append("Star Question 3")
            if not consent: missing.append("Consent Checkbox")

            if len(missing) > 0:
                st.error(f"⚠️ You cannot join yet! Please answer: {', '.join(missing)}")
            else:
            # --- VALIDATION PASSED ---
                try:
                    supabase.table('participants').insert({
                        'email': new_email, 'name': new_name, 'passphrase': new_phrase,
                        'clue_1': c1, 'clue_2': c2, 'clue_3': c3,
                        'star_q1': sq1, 'star_q2': sq2, 'star_q3': sq3
                    }).execute()
                    st.success("Signed up! Please Log In.")
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    # B. LOGGED IN DASHBOARD
    user = st.session_state.user
    
    st.info("📅 **Event:** 23rd Dec 2025 | ⏰ **5:00 PM** | 📍 **M8 Meeting Room**")
    
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
            if stage == 'signup':
                if st.button("Generate Assignments (Exclude Me)"):
                    run_assignment()
            else:
                st.warning("Assignments Locked.")
            
            st.write("---")
            st.write("**Game Flow Control**")
            stage_order = ['signup', 'token_reveal', 'gift_hunt', 'star_voting', 'grand_reveal']
            new_stage = st.selectbox("Set Stage", stage_order)
            
            if st.button("Update Stage"):
                set_config('stage', new_stage)
                st.rerun()
                
            if stage == 'grand_reveal':
                 st.write("---")
                 if st.button("🚀 TRIGGER FINAL BALLOONS"):
                     st.balloons()

        with col2:
             st.write("**Participant Status**")
             all_users = supabase.table('participants').select('email, name').eq('is_admin', False).execute().data
             all_assigns = supabase.table('assignments').select('*').execute().data
             
             status_data = []
             for u in all_users:
                 assign = next((a for a in all_assigns if a['recipient_email'] == u['email']), None)
                 token = assign['recipient_token'] if assign else "-"
                 status_data.append({"Name": u['name'], "Token": token})
             
             st.dataframe(pd.DataFrame(status_data), hide_index=True)

    st.divider()

    # --- PARTICIPANT VIEW ---
    if not user['is_admin']:
        
        # 1. WAITING ROOM
        if stage == 'signup':
            st.subheader("☕ The Waiting Room")
            st.warning("All the users have not signed up yet! Please wait.")
            st.write("### Who is already here?")
            participants = supabase.table('participants').select('name').eq('is_admin', False).execute().data
            for p in participants:
                st.write(f"- {p['name']}")
            st.caption("Refresh occasionally.")
            st.stop()

        assignment = get_assignment(user['email'])
        if not assignment:
            st.error("Game Started. You have no assignment (Late signup?).")
            st.stop()
            
        target = get_user_by_email(assignment['recipient_email'])
        
        # --- TABS ---
        tab_santa, tab_recipient, tab_leaderboard, tab_star, tab_help = st.tabs(["🎅 My Mission", "🎁 My Gift", "🏆 Speed Winners", "🌟 Star Game", "❓ Help"])

        # --- TAB 1: SANTA MISSION (BLIND) ---
        with tab_santa:
            st.subheader("YOUR MISSION")
            
            if stage == 'token_reveal':
                st.markdown(f"### 🏷️ Gift Token: `{assignment['recipient_token']}`")
                st.warning("You do NOT know who this person is! Read the clues and buy a gift that fits their vibe.")
                st.info("On Event Day, write this Token Number on the gift and place it on the table.")
            elif stage in ['gift_hunt', 'star_voting']:
                st.markdown(f"### 🏷️ Gift Token: `{assignment['recipient_token']}`")
                st.success("Gift should be on the table now!")
            elif stage == 'grand_reveal':
                st.success(f"You were the Santa for: **{target['name']}**!")

            st.divider()
            st.write("🕵️ **Target Persona (Clues)**")
            st.info(f"**Habit:** {target['clue_1']}")
            st.info(f"**Mood Lifter:** {target['clue_2']}")
            st.info(f"**Wishlist:** {target['clue_3']}")
            
            st.divider()
            st.write("📝 **Leave a Clue About YOURSELF**")
            sc1 = st.text_input("Your Clue", value=assignment.get('santa_clue_1') or "")
            if st.button("Save My Identity Clue"):
                supabase.table('assignments').update({'santa_clue_1': sc1}).eq('santa_email', user['email']).execute()
                st.toast("Clue Saved!")

        # --- TAB 2: RECIPIENT BOX ---
        with tab_recipient:
            my_row = supabase.table('assignments').select('*').eq('recipient_email', user['email']).execute().data[0]
            
            if stage == 'token_reveal':
                st.info("Wait for the Admin to start the Gift Hunt!")
            
            elif stage in ['gift_hunt', 'star_voting', 'grand_reveal']:
                st.markdown(f"# 🎫 Your Token: `{my_row['recipient_token']}`")
                st.write("Go find the gift with this number on it!")
                st.divider()

                status = my_row['status']
                guesses_used = my_row.get('guess_count', 0)
                
                if status == 'assigned':
                    st.button("📦 I found & RECEIVED my gift", 
                              on_click=lambda: supabase.table('assignments').update({'status': 'received'}).eq('recipient_email', user['email']).execute())
                
                elif status == 'received':
                    st.success("Gift in hand!")
                    if st.button("🎁 I have OPENED my gift"):
                         supabase.table('assignments').update({'status': 'opened'}).eq('recipient_email', user['email']).execute()
                         st.rerun()

                elif status in ['opened', 'revealed']:
                    st.success("Gift Opened! Guess your Santa!")
                    
                    st.write("#### 🕵️ Clue from your Santa:")
                    if my_row['santa_clue_1']: st.info(f"\"{my_row['santa_clue_1']}\"")
                    else: st.warning("(Santa left no clue!)")
                    
                    if not my_row.get('is_correct_guess') and guesses_used < 2:
                        st.write("#### ⚡ Fastest Finger First!")
                        people = get_all_participants_names()
                        options = {p['name']: p['email'] for p in people if p['email'] != user['email'] and p['email'] != my_row.get('first_wrong_guess')}
                        guess_name = st.selectbox("Who is it?", ["Select..."] + list(options.keys()))
                        
                        if st.button("🔒 Lock In Guess"):
                            if guess_name != "Select...":
                                guessed_email = options[guess_name]
                                is_correct = (guessed_email == my_row['santa_email'])
                                update_data = {'guess_count': guesses_used + 1, 'guess_timestamp': datetime.now(timezone.utc).isoformat()}
                                if is_correct:
                                    update_data['is_correct_guess'] = True
                                    update_data['guess_email'] = guessed_email
                                else:
                                    if guesses_used == 0: update_data['first_wrong_guess'] = guessed_email
                                supabase.table('assignments').update(update_data).eq('recipient_email', user['email']).execute()
                                st.rerun()
                                
                    elif my_row.get('is_correct_guess'):
                         st.success("✅ CORRECT!")
                         if stage == 'grand_reveal':
                            santa_info = get_user_by_email(my_row['santa_email'])
                            st.balloons()
                            st.markdown(f"### Santa: **{santa_info['name']}**")
                    else:
                        st.error("❌ Out of guesses!")
                        if stage == 'grand_reveal':
                            santa_info = get_user_by_email(my_row['santa_email'])
                            st.balloons()
                            st.markdown(f"### Santa: **{santa_info['name']}**")

        # --- TAB 3: SPEED WINNERS ---
        with tab_leaderboard:
            st.subheader("🏆 Top 5 Speed Winners")
            response = supabase.table('assignments').select('recipient_email, guess_timestamp, is_correct_guess').execute()
            
            top_5_emails = [] 
            if response.data:
                 guessed_only = [d for d in response.data if d['guess_timestamp'] is not None]
                 correct_guesses = [d for d in guessed_only if d['is_correct_guess']]
                 correct_guesses.sort(key=lambda x: x['guess_timestamp'])
                 
                 top_5_emails = [x['recipient_email'] for x in correct_guesses[:5]]
                 
                 if not correct_guesses:
                     st.write("No correct guesses yet...")
                 else:
                     for idx, entry in enumerate(correct_guesses):
                         user_info = get_user_by_email(entry['recipient_email'])
                         if user_info:
                             rank = idx + 1
                             medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                             if rank <= 5:
                                 st.write(f"### {medal} {user_info['name']}")
                             if rank == 5:
                                 st.caption("--- WINNERS CIRCLE CLOSED ---")

        # --- TAB 4: STAR GAME (VOTING) ---
        with tab_star:
            st.subheader("🌟 The Secret Santa Star")
            
            if stage != 'star_voting' and stage != 'grand_reveal':
                st.info("This game unlocks after the gifts are opened!")
            else:
                top_5 = calculate_top_5_speed_winners()
                
                if user['email'] in top_5:
                    st.success("🏆 You are a Speed Winner! You are watching from the VIP Lounge.")
                    st.write("The remaining players are voting for the Star...")
                else:
                    st.write("Vote for the person with the most interesting answers!")
                    st.caption("You cannot vote for yourself.")
                    
                    my_vote = supabase.table('votes').select('*').eq('voter_email', user['email']).execute().data
                    
                    if my_vote:
                        st.success("✅ Vote Cast! Waiting for results.")
                    else:
                        candidates = supabase.table('participants').select('*').eq('is_admin', False).execute().data
                        # FILTER: Exclude Top 5 AND Exclude Self
                        valid_candidates = [c for c in candidates if c['email'] not in top_5 and c['email'] != user['email']]
                        
                        vote_choice = st.selectbox("Choose a Profile to Review:", ["Select..."] + [f"Anonymous Profile {i+1}" for i in range(len(valid_candidates))])
                        
                        if vote_choice != "Select...":
                            idx = int(vote_choice.split(" ")[2]) - 1
                            cand = valid_candidates[idx]
                            
                            st.info("👇 Read their Answers below and Vote if you like them!")
                            st.markdown(f"""
                            <div style="background-color:#262730; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #4B4B4B;">
                                <p style="color:#FFA500;"><strong>Q1: Secretly Enjoys?</strong></p>
                                <p>{cand['star_q1']}</p>
                                <hr>
                                <p style="color:#FFA500;"><strong>Q2: Wrong Assumption?</strong></p>
                                <p>{cand['star_q2']}</p>
                                <hr>
                                <p style="color:#FFA500;"><strong>Q3: Weekend Hideout?</strong></p>
                                <p>{cand['star_q3']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button("⭐ Vote for this Profile"):
                                supabase.table('votes').insert({'voter_email': user['email'], 'voted_for_email': cand['email']}).execute()
                                st.rerun()

                if stage == 'grand_reveal':
                    st.divider()
                    st.subheader("🌟 AND THE STAR IS...")
                    
                    votes = supabase.table('votes').select('voted_for_email').execute().data
                    if votes:
                        vote_counts = pd.Series([v['voted_for_email'] for v in votes]).value_counts()
                        winner_email = vote_counts.idxmax()
                        winner_info = get_user_by_email(winner_email)
                        
                        st.balloons()
                        st.markdown(f"# 🌟 {winner_info['name']} 🌟")
                        st.write(f"With {vote_counts.max()} votes!")
                    else:
                        st.write("No votes cast yet.")

        # --- TAB 5: HELP ---
        with tab_help:
            st.header("📖 How to Play")
            st.info("This is a **Double-Blind** Secret Santa!")
            st.subheader("1️⃣ Before Event")
            st.markdown("- Sign up and answer the questions.")
            st.markdown("- **Santa's Mission:** You get a Token #. Buy a gift for that persona.")
            st.subheader("2️⃣ On Event Day")
            st.markdown("- **Token Reveal:** Write your Token # on the gift.")
            st.markdown("- **Gift Hunt:** Find the gift with your Token #.")
            st.markdown("- **Speed Game:** Guess Santa FAST! Top 5 win.")
            st.subheader("3️⃣ The Star Game")
            st.markdown("- **Top 5 Speed Winners** are VIP Spectators.")
            st.markdown("- **Everyone Else:** Votes for the best anonymous answers.")
            st.markdown("- The Winner becomes the **Secret Santa Star**!")
