# leprendix/services/teamup.py
import datetime
import requests
from tkinter import messagebox
from leprendix.core.config_loader import CONFIG

def search_teamup_events(search_term, start_date=None, end_date=None, mode='standard'):
    """
    Sucht Teamup-Kalendereinträge basierend auf dem Titel/Notizen.
    """
    
    # Lade Konfiguration dynamisch
    api_key = CONFIG.get('TEAMUP_API_KEY', '')
    calendar_id = CONFIG.get('TEAMUP_CALENDAR_ID', '')
    
    clean_api_key = api_key.strip()
    base_url = f"https://api.teamup.com/{calendar_id}/events"
    
    headers = {
        'Teamup-Token': clean_api_key, 
        'Accept': 'application/json'
    }
    
    # BEGRENZUNG DES ZEITRAUMS
    if start_date is None:
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = (datetime.date.today() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
    params = {
        'startDate': start_date,
        'endDate': end_date
    }
    
    try:
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()  
        
        data = response.json()
        
        matching_events = []
        term = search_term.lower()

        for event in data.get('events', []):
            title = event.get('title', '')
            notes = event.get('notes', '')
            is_match = False

            if mode == 'gemeinde':
                # Suche nach Nachname UND (1x, 2x, 3x, 4x, 5x im Titel)
                t_low = title.lower()
                has_name = term in t_low or term in notes.lower()
                has_x = any(x in t_low for x in ["1x", "2x", "3x", "4x", "5x"])
                
                if has_name and has_x:
                    is_match = True
            else:
                if term in title.lower() or term in notes.lower():
                    is_match = True
            
            if is_match:
                
                start_iso = event.get('start_dt')
                end_iso = event.get('end_dt')
                
                if start_iso and end_iso:
                    start_iso_clean = start_iso.replace('Z', '+00:00')
                    end_iso_clean = end_iso.replace('Z', '+00:00')
                    
                    start_dt = datetime.datetime.fromisoformat(start_iso_clean)
                    end_dt = datetime.datetime.fromisoformat(end_iso_clean)
                    
                    event_tuple = (
                        title, 
                        start_dt.strftime('%d.%m.%Y'),
                        start_dt.strftime('%H:%M'),
                        end_dt.strftime('%H:%M')
                    )
                    matching_events.append(event_tuple)
                    
        return matching_events
        
    except requests.exceptions.HTTPError as e:
        error_details = response.text if hasattr(response, 'text') else str(e)
        messagebox.showerror("API Fehler", f"HTTP-Fehler beim Abruf der Teamup-Daten: {e}\nDetails: {error_details}")
        return []
    except Exception as e:
        messagebox.showerror("Fehler", f"Teamup API-Fehler: {e}")
        return []