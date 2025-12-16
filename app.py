import streamlit as st
from supabase import create_client, Client
import random
import time

# --- SETUP ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except:
    st.error("Secrets not found. Please set SUPABASE_URL and SUPABASE_KEY in Streamlit settings.")
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
    if res.data:
        return res.data[0]
    return None

def get_user_by_email(email):
    res = supabase.table('participants').select('*').eq('email', email).execute()
    return res.data[0] if res.data else None

def run_assignment():
    users = supabase.table('participants').select('email').execute()
    emails = [u['email'] for u in users.data]
    
    if len(emails) < 2:
        st.error("Need at least 2 people!")
        return

    santas = emails.copy()
    recipients = emails.copy()
    
    # Simple retry logic to ensure no one gets themselves
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
    
    # Clear old assignments if any (for safety in this demo script)
    supabase.table('assignments').delete().neq('status', 'impossible_value').execute()
    
    supabase.table('assignments').insert(data).execute()
    set_config('stage', 'clue_1')
    st.success("Assignments generated! Stage moved to Clue 1.")

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
        new_name = st.text_input("Full Name")
        new_email = st.text_input("Email", key="signup_email").lower().strip()
        new_phrase = st.text_input("Create Passphrase", type="password")
        c1 = st.text_input("Clue 1: A hobby or interest")
        c2 = st.text_input("Clue 2: Something specific you like")
        c3 = st.text_input("Clue 3: Describe your vibe in 3 words")
        consent = st.checkbox("I promise to play nicely and keep secrets.")
        
        if st.button("Join the Party"):
            if consent and new_email and new_phrase:
                try:
                    supabase.table('participants').insert({
                        'email': new_email, 'name': new_name, 'passphrase': new_phrase,
                        'clue_1': c1, 'clue_2': c2, 'clue_3': c3
                    }).execute()
                    st.success("Signed up! Please Log In.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Fill all fields and accept the rules.")

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
            if st.button("Generate Assignments"):
                run_assignment()
                
            new_stage = st.selectbox("Manually Set Stage", 
                ['signup', 'clue_1', 'clue_2', 'clue_3', 'name_reveal', 'event_day', 'grand_reveal'])
            if st.button("Update Stage"):
                set_config('stage', new_stage)
                st.rerun()

        with col2:
             # Progress Tracker
             all_assigns = supabase.table('assignments').select('status').execute().data
             total = len(all_assigns)
             if total > 0:
                 opened_count = sum(1 for x in all_assigns if x['status'] in ['opened', 'revealed'])
                 received_count = sum(1 for x in all_assigns if x['status'] in ['received', 'opened', 'revealed'])
                 
                 st.metric("Gifts Received", f"{received_count}/{total}")
                 st.metric("Gifts Opened", f"{opened_count}/{total}")
                 
                 # THE BIG BUTTON
                 st.write("---")
                 if opened_count == total:
                     st.success("All gifts opened! Ready for reveal.")
                 else:
                     st.warning("Wait until all gifts are opened.")
                     
                 if st.button("🚀 TRIGGER GRAND REVEAL"):
                     set_config('stage', 'grand_reveal')
                     st.rerun()

    st.divider()

    # --- USER DASHBOARD ---
    if stage == 'signup':
        st.info("Waiting for everyone to sign up... 🕒")
    
    else:
        assignment = get_assignment(user['email'])
        if not assignment:
            st.error("No assignment found. Ask Admin.")
            st.stop()
            
        target = get_user_by_email(assignment['recipient_email'])
        
        # --- TAB A: MY MISSION (SANTA) ---
        st.subheader("🎅 Your Santa Mission")
        
        if stage in ['clue_1', 'clue_2', 'clue_3']:
            st.write("🕵️ **Target Identity: HIDDEN**")
            st.info(f"Clue 1: {target['clue_1']}")
            if stage in ['clue_2', 'clue_3']:
                st.info(f"Clue 2: {target['clue_2']}")
            if stage == 'clue_3':
                st.info(f"Clue 3: {target['clue_3']}")
                
        elif stage in ['name_reveal', 'event_day', 'grand_reveal']:
            st.success(f"🎯 You are buying for: **{target['name']}**")
            
            # Gift Story Input
            if stage != 'grand_reveal':
                with st.expander("Write Gift Story (Optional)"):
                    st.caption("This appears on their screen after they open the gift.")
                    title = st.text_input("Gift Title", value=assignment.get('gift_story_title') or "")
                    body = st.text_area("Why you chose this...", value=assignment.get('gift_story_body') or "")
                    if st.button("Save Story"):
                        supabase.table('assignments').update({'gift_story_title': title, 'gift_story_body': body}).eq('santa_email', user['email']).execute()
                        st.toast("Story Saved!")

        # --- TAB B: MY INBOX (RECIPIENT) ---
        if stage in ['event_day', 'grand_reveal']:
            st.divider()
            st.subheader("🎁 Your Inbox")
            
            # Fetch my status
            my_row = supabase.table('assignments').select('*').eq('recipient_email', user['email']).execute().data[0]
            status = my_row['status']
            
            # Logic for receiving/opening
            if stage == 'event_day':
                if status == 'assigned':
                    st.info("Waiting for you to get the gift...")
                    if st.button("📦 I have RECEIVED my gift"):
                        supabase.table('assignments').update({'status': 'received'}).eq('recipient_email', user['email']).execute()
                        st.rerun()
                
                elif status == 'received':
                    st.success("Gift in hand! Open it now!")
                    if st.button("🎁 I have OPENED my gift"):
                        supabase.table('assignments').update({'status': 'opened'}).eq('recipient_email', user['email']).execute()
                        st.rerun()
                
                elif status == 'opened':
                    # Story Reveal
                    if my_row['gift_story_title']:
                        st.write(f"**{my_row['gift_story_title']}**")
                        st.write(f"_{my_row['gift_story_body']}_")
                    
                    st.warning("👀 Waiting for Admin to trigger the Grand Reveal...")
                    st.caption("Once everyone has opened their gifts, the admin will press the button.")

            # GRAND REVEAL LOGIC
            elif stage == 'grand_reveal':
                santa_info = get_user_by_email(my_row['santa_email'])
                
                st.balloons()
                st.markdown(f"### Your Secret Santa was...")
                time.sleep(1) # Dramatic pause
                st.markdown(f"# 🌟 {santa_info['name']} 🌟")
                
                if my_row['gift_story_title']:
                    st.write("---")
                    st.write(f"**{my_row['gift_story_title']}**")
                    st.write(f"_{my_row['gift_story_body']}_")
