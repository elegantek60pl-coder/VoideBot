import os
from dotenv import load_dotenv
from keep_alive import keep_alive
import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import asyncio

# Ładujemy zmienne
load_dotenv()

# --- KONFIGURACJA (ZAKTUALIZOWANA) ---
TOKEN = os.environ.get("TOKEN")

GUILD_ID = 1457834566617403484
ROLE_ID_USER = 1457834566617403490
CHANNEL_WELCOME_ID = 1457834567003144252
CATEGORY_TICKET_ID = 1457834568080949255
CHANNEL_LEGIT_ID = 1457834567456133207
ROLE_ID_ACCESS = 1457834566617403487

# --- KOLOR ---
THEME_COLOR = discord.Color.from_str("#681CFD")

# --- ZMIENNE GLOBALNE ---
active_codes = {} # Tutaj trzymamy kody rabatowe: { "KOD": { "percent": 10, "expires": timestamp } }

# --- POMOCNICZE FUNKCJE ---
def convert_time_to_seconds(time_str):
    """Zamienia tekst np. '1h' na sekundy"""
    unit = time_str[-1:].lower() # Ostatni znak (np. 'h')
    try:
        val = int(time_str[:-1]) # Liczba (np. 1)
    except:
        if time_str.isdigit(): return int(time_str) # Jeśli podano samą liczbę, uznaj jako sekundy
        return None

    if unit == 's': return val
    elif unit == 'm': return val * 60
    elif unit == 'h': return val * 3600
    elif unit == 'd': return val * 86400
    elif unit == 'o': return val * 2592000 # 'ms' jako miesiąc (oznaczenie 'o' w kodzie dla uproszczenia parsowania, ale obsłużymy 'ms' w komendzie)
    elif unit == 'r': return val * 31536000
    return None

def parse_duration_input(time_str):
    # Obsługa 'ms' jako miesiąc
    if time_str.endswith("ms"):
        return int(time_str[:-2]) * 2592000
    return convert_time_to_seconds(time_str)


# --- WIDOKI I KLASY ---

# 1. WERYFIKACJA
class VerifyModal(discord.ui.Modal, title="Weryfikacja"):
    answer = discord.ui.TextInput(label="Ile to jest 9 + 10?", placeholder="Wpisz wynik cyfrą...")
    async def on_submit(self, interaction: discord.Interaction):
        if self.answer.value.strip() == "19":
            role = interaction.guild.get_role(ROLE_ID_USER)
            if role:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Poprawna odpowiedź! Nadano dostęp.", ephemeral=True)
            else: await interaction.response.send_message("❌ Błąd roli.", ephemeral=True)
        else: await interaction.response.send_message("❌ Źle.", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Zweryfikuj się", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button): await interaction.response.send_modal(VerifyModal())

# 2. GIVEAWAY
class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Używamy ID wiadomości jako klucza, żeby rozróżnić konkursy, ale tutaj uprościmy
        # W prawdziwej bazie danych zapisywalibyśmy uczestników. Tutaj:
        # Ponieważ widok jest 'stateless' (bezstanowy) po restarcie, musimy polegać na reakcjach lub innej metodzie.
        # Jednak dla prostoty użyjemy przycisku, który dodaje ID usera do listy w pamięci bota (resetuje się po restarcie).
        # Aby to działało lepiej, po prostu dodamy przycisk, który wysyła ephemeral "Dołączyłeś".
        # Ale żeby losować, musimy zbierać userów.
        self.participants = set()

    @discord.ui.button(label="Dołącz", style=discord.ButtonStyle.primary, emoji="🎉", custom_id="join_giveaway")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("Już bierzesz udział!", ephemeral=True)
        
        self.participants.add(interaction.user.id)
        await interaction.response.send_message("✅ Dołączyłeś do konkursu!", ephemeral=True)
        # Aktualizujemy licznik na przycisku
        button.label = f"Dołącz ({len(self.participants)})"
        await interaction.message.edit(view=self)

# 3. KODY RABATOWE - MODAL
class DiscountModal(discord.ui.Modal, title="Wpisz kod rabatowy"):
    code_input = discord.ui.TextInput(label="Kod", placeholder="Np. LATO2024")

    async def on_submit(self, interaction: discord.Interaction):
        code = self.code_input.value.strip()
        now = datetime.datetime.now().timestamp()

        if code in active_codes:
            data = active_codes[code]
            if data['expires'] > now:
                # Kod ważny
                percent = data['percent']
                embed = discord.Embed(title="✅ Kod Aktywny!", color=discord.Color.green())
                embed.description = f"Użytkownik {interaction.user.mention} użył kodu **{code}**.\n\n📉 **Zniżka: {percent}%**"
                await interaction.channel.send(embed=embed)
                await interaction.response.send_message("Pomyślnie użyto kodu!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Ten kod wygasł.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nieprawidłowy kod.", ephemeral=True)

# 4. TICKET - STEROWANIE
class TicketControlView(discord.ui.View):
    def __init__(self, is_order=False):
        super().__init__(timeout=None)
        self.is_order = is_order
        
        # Jeśli to zamówienie, dodajemy przycisk kodu
        if is_order:
            self.add_item(self.discount_button)

    # Definiujemy przycisk kodu jako zmienną, żeby dodać go warunkowo
    @discord.ui.button(label="Użyj Kodu", style=discord.ButtonStyle.secondary, emoji="🏷️", custom_id="use_code", row=0)
    async def discount_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DiscountModal())

    @discord.ui.button(label="Zamknij", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket", row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_admin = interaction.user.guild_permissions.administrator
        if is_admin:
            await interaction.response.send_message("🗑️ Usuwanie kanału...")
            await asyncio.sleep(2)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("🔒 Zamykam dostęp.", ephemeral=True)
            await interaction.channel.set_permissions(interaction.user, read_messages=False, send_messages=False)
            await interaction.channel.send(embed=discord.Embed(description=f"🔒 {interaction.user.mention} zamknął zgłoszenie.", color=THEME_COLOR))

    @discord.ui.button(label="Przejmij", style=discord.ButtonStyle.success, emoji="✋", custom_id="claim_ticket", row=1)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔ Tylko admin!", ephemeral=True)
        await interaction.channel.send(embed=discord.Embed(description=f"✅ Przejęte przez: {interaction.user.mention}", color=THEME_COLOR))
        button.disabled = True
        button.label = f"Przejął: {interaction.user.display_name}"
        await interaction.message.edit(view=self)

# 5. TICKET - WYBÓR
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Zamówienie", description="Chcę złożyć zamówienie", emoji="🛒", value="order"),
            discord.SelectOption(label="Pomoc", description="Potrzebuję pomocy", emoji="❓", value="help"),
            discord.SelectOption(label="Pytanie", description="Mam pytanie", emoji="❔", value="question"),
            discord.SelectOption(label="Problem z pluginem", description="Błąd w pluginie", emoji="🔌", value="plugin"),
            discord.SelectOption(label="Inne", description="Inna sprawa", emoji="📝", value="other"),
        ]
        super().__init__(placeholder="Wybierz kategorię...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(CATEGORY_TICKET_ID)
        if not category: return await interaction.response.send_message("❌ Błąd kategorii.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        await interaction.response.send_message(f"✅ Utworzono: {ticket_channel.mention}", ephemeral=True)
        
        selected = self.values[0]
        labels = {"order": "Zamówienie", "help": "Pomoc", "question": "Pytanie", "plugin": "Problem", "other": "Inne"}
        
        embed = discord.Embed(title="Zgłoszenie", description=f"Witaj {interaction.user.mention}!\nOpisz sprawę.\nKategoria: **{labels.get(selected)}**", color=THEME_COLOR)
        
        # SPRAWDZAMY CZY TO ZAMÓWIENIE -> JEŚLI TAK, DAJEMY WIDOK Z KODEM RABATOWYM
        is_order_ticket = (selected == "order")
        view = TicketControlView(is_order=is_order_ticket)
        
        await ticket_channel.send(embed=embed, view=view)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# 6. ACCESS VIEW (/nadaj)
class AccessView(discord.ui.View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
    
    # ... (Tu kod z poprzedniej odpowiedzi, Modal odrzucania itp. Dla oszczędności miejsca skróciłem, ale wklej pełny z poprzedniej odpowiedzi jeśli chcesz modale odrzucania) ...
    # Zostawiam wersję z Modalami odrzucania dla kompletności:
    
    @discord.ui.button(label="Nadaj dostęp", style=discord.ButtonStyle.success, emoji="✅", custom_id="access_grant")
    async def grant(self, interaction: discord.Interaction, button):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔ Tylko Admin", ephemeral=True)
        member = interaction.guild.get_member(self.target_user_id)
        role = interaction.guild.get_role(ROLE_ID_ACCESS)
        if member and role:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Nadano dostęp dla {member.mention}", ephemeral=True)
            button.disabled = True; self.children[1].disabled = True; button.label="Nadano"
            await interaction.message.edit(view=self)
            try: await member.send(f"🎉 Dostęp nadany na **{interaction.guild.name}**!")
            except: pass
        else: await interaction.response.send_message("❌ Błąd usera/roli", ephemeral=True)

    @discord.ui.button(label="Brak wymagań", style=discord.ButtonStyle.danger, emoji="❌", custom_id="access_deny")
    async def deny(self, interaction: discord.Interaction, button):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔ Tylko Admin", ephemeral=True)
        await interaction.response.send_modal(RejectModal(self, self.target_user_id))

class RejectModal(discord.ui.Modal, title="Powód odrzucenia"):
    reason = discord.ui.TextInput(label="Powód", style=discord.TextStyle.paragraph)
    def __init__(self, view, uid): super().__init__(); self.view=view; self.uid=uid
    async def on_submit(self, interaction):
        member = interaction.guild.get_member(self.uid)
        self.view.children[0].disabled=True; self.view.children[1].disabled=True; self.view.children[1].label="Odrzucono"
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message(f"❌ Odrzucono. Powód: {self.reason.value}", ephemeral=True)
        if member: 
            try: await member.send(f"❌ Weryfikacja odrzucona. Powód: {self.reason.value}")
            except: pass

# 7. LEGIT CHECK
class LegitModal(discord.ui.Modal, title="Oceń transakcję"):
    cena = discord.ui.TextInput(label="Cena (1-10)", max_length=2); dostawa = discord.ui.TextInput(label="Dostawa (1-10)", max_length=2); obsluga = discord.ui.TextInput(label="Obsługa (1-10)", max_length=2); opis = discord.ui.TextInput(label="Komentarz", style=discord.TextStyle.paragraph)
    def __init__(self, view): super().__init__(); self.view=view
    async def on_submit(self, itr):
        try:
            c,d,o = int(self.cena.value), int(self.dostawa.value), int(self.obsluga.value)
            if not (1<=c<=10 and 1<=d<=10 and 1<=o<=10): raise ValueError
            avg = round((c+d+o)/3,1)
            chn = itr.guild.get_channel(CHANNEL_LEGIT_ID)
            embed = discord.Embed(title="✅ LEGIT CHECK", color=THEME_COLOR)
            embed.add_field(name="Klient", value=itr.user.mention, inline=False)
            embed.add_field(name="Oceny", value=f"💸 {c}/10 | 🚚 {d}/10 | 📞 {o}/10", inline=False)
            embed.add_field(name="Komentarz", value=self.opis.value, inline=False)
            embed.set_footer(text=f"Średnia: {avg}/10 {'⭐'*int(avg)}")
            if chn: await chn.send(embed=embed)
            try:
                if "-" in chn.name:
                    p, n = chn.name.rsplit("-", 1)
                    if n.isdigit(): await chn.edit(name=f"{p}-{int(n)+1}")
            except: pass
            self.view.clear_items(); self.view.add_item(discord.ui.Button(label="Wystawiono", disabled=True))
            await itr.response.edit_message(content="✅ Dzięki!", view=self.view)
        except: await itr.response.send_message("❌ Liczby 1-10!", ephemeral=True)
class RoleLegitView(discord.ui.View):
    def __init__(self, r): super().__init__(timeout=None); self.r=r
    @discord.ui.button(label="Oceń", style=discord.ButtonStyle.primary, emoji="⭐")
    async def rate(self, itr, btn):
        if self.r not in itr.user.roles: return await itr.response.send_message("⛔ Brak roli", ephemeral=True)
        await itr.response.send_modal(LegitModal(self))


# --- BOT SETUP ---
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.all()); self.synced=False
    async def setup_hook(self):
        self.add_view(VerifyView())
        self.add_view(TicketView())
        self.add_view(TicketControlView(is_order=False)) # Rejestrujemy ogólny
        self.add_view(TicketControlView(is_order=True))  # Rejestrujemy ten z kodem
        print("🔄 Widoki OK.")
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced: await self.tree.sync(guild=discord.Object(id=GUILD_ID)); self.synced=True
        print(f"✅ Zalogowano: {self.user}")
bot = MyBot()


# --- KOMENDY ---

# 1. KONKURS (GIVEAWAY)
@bot.tree.command(name="konkurs", description="[ADMIN] Rozpocznij giveaway", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nagroda="Co można wygrać?", czas="Ile czasu? (np. 1h, 30m)", ile_osob="Ilu zwycięzców?")
async def konkurs(interaction: discord.Interaction, nagroda: str, czas: str, ile_osob: int = 1):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔ Brak uprawnień.", ephemeral=True)
    
    seconds = parse_duration_input(czas)
    if not seconds:
        return await interaction.response.send_message("❌ Nieprawidłowy format czasu! Użyj np. `1h`, `30m`, `1d`.", ephemeral=True)

    # Koniec czasu timestamp
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    timestamp = int(end_time.timestamp())

    embed = discord.Embed(title="🎉 KONKURS 🎉", description=f"Do wygrania: **{nagroda}**", color=THEME_COLOR)
    embed.add_field(name="⏳ Koniec", value=f"<t:{timestamp}:R> (<t:{timestamp}:F>)", inline=False)
    embed.add_field(name="🏆 Zwycięzców", value=str(ile_osob), inline=True)
    embed.set_footer(text="Kliknij przycisk, aby dołączyć!")

    view = GiveawayView()
    await interaction.response.send_message("Rozpoczynam konkurs!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=view)

    # Czekamy
    await asyncio.sleep(seconds)

    # Losowanie
    participants_list = list(view.participants)
    
    if len(participants_list) < ile_osob:
        await interaction.channel.send(f"❌ Konkurs na **{nagroda}** anulowany - zbyt mało uczestników.")
    else:
        winners = random.sample(participants_list, ile_osob)
        winners_mentions = ", ".join([f"<@{uid}>" for uid in winners])
        
        win_embed = discord.Embed(title="🎉 WYNIKI KONKURSU 🎉", color=discord.Color.gold())
        win_embed.description = f"Nagroda: **{nagroda}**\n\n🏆 **Zwycięzcy:** {winners_mentions}"
        win_embed.set_footer(text=f"Gratulacje!")
        
        await interaction.channel.send(content=winners_mentions, embed=win_embed)
        
    # Edytujemy stary embed, że zakończony
    embed.title = "🎉 KONKURS ZAKOŃCZONY 🎉"
    embed.color = discord.Color.dark_gray()
    view.children[0].disabled = True
    await msg.edit(embed=embed, view=view)


# 2. KODY RABATOWE
@bot.tree.command(name="ustaw_kod", description="[ADMIN] Dodaj kod rabatowy", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(kod="Treść kodu (np. LATO)", czas="Czas działania (s,m,h,d,ms,r)", procent="Wartość zniżki (%)")
async def ustaw_kod(interaction: discord.Interaction, kod: str, czas: str, procent: int):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔ Brak uprawnień.", ephemeral=True)

    seconds = parse_duration_input(czas)
    if not seconds:
        return await interaction.response.send_message("❌ Zły format czasu! (s, m, h, d, ms, r)", ephemeral=True)

    expiry = datetime.datetime.now().timestamp() + seconds
    
    # Zapisujemy kod
    active_codes[kod] = {
        "percent": procent,
        "expires": expiry
    }

    embed = discord.Embed(title="✅ Ustawiono Kod Rabatowy", color=discord.Color.green())
    embed.add_field(name="Kod", value=kod, inline=True)
    embed.add_field(name="Zniżka", value=f"{procent}%", inline=True)
    embed.add_field(name="Wygasa", value=f"<t:{int(expiry)}:R>", inline=False)
    
    await interaction.response.send_message(embed=embed)


# 3. POZOSTAŁE (NADAJ, SETUPY, PV...)
@bot.tree.command(name="nadaj", description="[ADMIN] Panel nadawania dostępu", guild=discord.Object(id=GUILD_ID))
async def nadaj(interaction: discord.Interaction, uzytkownik: discord.Member, zrzut_ekranu: discord.Attachment):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔", ephemeral=True)
    embed = discord.Embed(title="VoidCode - Darmowe Skrypty/Pluginy", color=THEME_COLOR)
    embed.description = f"**Autor:** {uzytkownik.mention}"; embed.set_image(url=zrzut_ekranu.url)
    embed.set_footer(text=f"ID: {interaction.id} • {datetime.datetime.now().strftime('%H:%M')}")
    await interaction.channel.send(embed=embed, view=AccessView(uzytkownik.id))
    await interaction.response.send_message("✅", ephemeral=True)

@bot.tree.command(name="setup_tickety", description="Setup Ticketów", guild=discord.Object(id=GUILD_ID))
async def setup_ticket(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    desc = """ᴡɪᴛᴀᴊ, ᴘᴏᴛʀᴢᴇʙᴜᴊᴇꜱᴢ ᴘᴏᴍᴏᴄʏ? ᴄʜᴄᴇꜱᴢ ᴄᴏꜱ ᴢᴀᴍᴏᴡɪᴄ?
ᴍᴀꜱᴢ ᴘʏᴛᴀɴɪᴇ ʟᴜʙ ᴘʀᴏʙʟᴇᴍ?
ᴡʏʙɪᴇʀᴢ ᴋᴀᴛᴇɢᴏʀɪᴇ ᴛɪᴄᴋᴇᴛᴜ ᴘᴏᴅ ꜱᴘᴏᴅᴇᴍ.

ᴘʀᴢʏᴘᴏᴍɪɴᴀᴍʏ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴄᴊᴀ ᴍᴀ ꜱᴡᴏᴊᴇ ᴘʀʏᴡᴀᴛɴᴇ ᴢʏᴄɪᴇ ɪ ɴɪᴇ ᴢᴀᴡꜱᴢᴇ ᴅᴏꜱᴛᴀɴɪᴇꜱᴢ ᴏᴅ ʀᴀᴢᴜ ᴏᴅᴘᴏᴡɪᴇᴅᴢ!"""
    embed = discord.Embed(title="STWÓRZ ZGŁOSZENIE", description=desc, color=THEME_COLOR)
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Gotowe", ephemeral=True)

@bot.tree.command(name="setup_weryfikacja", guild=discord.Object(id=GUILD_ID))
async def setup_verify(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    await interaction.channel.send(embed=discord.Embed(title="Weryfikacja", description="Kliknij.", color=THEME_COLOR), view=VerifyView())
    await interaction.response.send_message("OK", ephemeral=True)

@bot.tree.command(name="legit", guild=discord.Object(id=GUILD_ID))
async def legit(interaction: discord.Interaction, rola: discord.Role):
    if not interaction.user.guild_permissions.administrator: return
    await interaction.channel.send(embed=discord.Embed(title="Opinia", description=f"Rola: {rola.mention}", color=THEME_COLOR), view=RoleLegitView(rola))
    await interaction.response.send_message("OK", ephemeral=True)

@bot.tree.command(name="pv", guild=discord.Object(id=GUILD_ID))
async def pv(interaction: discord.Interaction, wiadomosc: str, uzytkownik: discord.Member = None, wszyscy: bool = False):
    if not interaction.user.guild_permissions.administrator: return
    await interaction.response.defer(ephemeral=True)
    if wszyscy:
        c=0
        for m in interaction.guild.members:
            if not m.bot:
                try: await m.send(f"🔔 **Ogłoszenie:**\n\n{wiadomosc}"); c+=1; await asyncio.sleep(2)
                except: pass
        await interaction.followup.send(f"Wysłano: {c}")
    elif uzytkownik:
        try: await uzytkownik.send(f"🔔 **Wiadomość:**\n\n{wiadomosc}"); await interaction.followup.send("Wysłano")
        except: await interaction.followup.send("Blokada PW")

@bot.tree.command(name="stworz_embed", guild=discord.Object(id=GUILD_ID))
async def create_embed(interaction: discord.Interaction, tytul: str, tresc: str, kolor: str = "#ffffff", plik: discord.Attachment = None, link: str = None):
    if not interaction.user.guild_permissions.administrator: return
    try:
        embed = discord.Embed(title=tytul, description=tresc.replace("\\n", "\n"), color=int(kolor.replace("#",""),16))
        if plik: embed.set_image(url=plik.url)
        elif link: embed.set_image(url=link)
        await interaction.channel.send(embed=embed); await interaction.response.send_message("OK", ephemeral=True)
    except: await interaction.response.send_message("Błąd", ephemeral=True)

# Start
keep_alive()
if TOKEN: bot.run(TOKEN)