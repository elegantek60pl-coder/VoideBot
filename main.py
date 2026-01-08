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

# --- KONFIGURACJA ---
TOKEN = os.environ.get("TOKEN")

GUILD_ID = 1457834566617403484
ROLE_ID_USER = 1457834566617403490
CHANNEL_WELCOME_ID = 1457834567003144252
CATEGORY_TICKET_ID = 1457834568080949255
CHANNEL_LEGIT_ID = 1457834567456133207
ROLE_ID_ACCESS = 1457834566617403487

# --- KOLOR ---
THEME_COLOR = discord.Color.from_str("#681CFD")

# --- ZMIENNE GLOBALNE (KODY) ---
active_codes = {} 

# --- POMOCNICZE FUNKCJE ---
def parse_duration_input(time_str):
    unit = time_str[-1:].lower()
    try: val = int(time_str[:-1])
    except: return int(time_str) if time_str.isdigit() else None
    
    seconds = 0
    if unit == 's': seconds = val
    elif unit == 'm': seconds = val * 60
    elif unit == 'h': seconds = val * 3600
    elif unit == 'd': seconds = val * 86400
    elif unit == 'r': seconds = val * 31536000
    elif unit == 's' and time_str.endswith("ms"): seconds = int(time_str[:-2]) * 2592000 
    else: return None
    return seconds

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
        self.participants = set()

    @discord.ui.button(label="Dołącz", style=discord.ButtonStyle.primary, emoji="🎉", custom_id="join_giveaway")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("Już bierzesz udział!", ephemeral=True)
        self.participants.add(interaction.user.id)
        await interaction.response.send_message("✅ Dołączyłeś!", ephemeral=True)
        button.label = f"Dołącz ({len(self.participants)})"
        await interaction.message.edit(view=self)

# 3. KODY RABATOWE
class DiscountModal(discord.ui.Modal, title="Wpisz kod rabatowy"):
    code_input = discord.ui.TextInput(label="Kod", placeholder="Np. LATO2024")
    async def on_submit(self, interaction: discord.Interaction):
        code = self.code_input.value.strip()
        now = datetime.datetime.now().timestamp()
        if code in active_codes:
            data = active_codes[code]
            if data['expires'] > now:
                embed = discord.Embed(title="✅ Kod Aktywny!", color=discord.Color.green())
                embed.description = f"Użytkownik {interaction.user.mention} użył kodu **{code}**.\n\n📉 **Zniżka: {data['percent']}%**"
                await interaction.channel.send(embed=embed)
                await interaction.response.send_message("Pomyślnie użyto kodu!", ephemeral=True)
            else: await interaction.response.send_message("❌ Ten kod wygasł.", ephemeral=True)
        else: await interaction.response.send_message("❌ Nieprawidłowy kod.", ephemeral=True)

class DeleteCodeButton(discord.ui.Button):
    def __init__(self, code_name):
        super().__init__(label=f"Usuń {code_name}", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id=f"del_{code_name}")
        self.code_name = code_name
    async def callback(self, interaction: discord.Interaction):
        if self.code_name in active_codes:
            del active_codes[self.code_name]
            await interaction.response.send_message(f"✅ Usunięto kod: **{self.code_name}**", ephemeral=True)
            self.view.remove_item(self)
            await interaction.message.edit(view=self.view)
        else: await interaction.response.send_message("❌ Ten kod już nie istnieje.", ephemeral=True)

class DeleteCodeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for code in active_codes:
            self.add_item(DeleteCodeButton(code))

# 4. TICKET - STEROWANIE
class TicketControlView(discord.ui.View):
    def __init__(self, is_order=False):
        super().__init__(timeout=None)
        self.is_order = is_order
        if not self.is_order:
            for child in self.children:
                if hasattr(child, "custom_id") and child.custom_id == "use_code":
                    self.remove_item(child)
                    break

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
            discord.SelectOption(label="Zamówienie", description="Chcesz złożyć zamówienie", emoji="🛒", value="order"),
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

        selected = self.values[0]
        prefix_map = {"order": "zamowienie", "help": "pomoc", "question": "pytanie", "plugin": "plugin", "other": "inne"}
        prefix = prefix_map.get(selected, "ticket")
        
        count = 1
        while True:
            name = f"ticket-{prefix}-{count}"
            if not discord.utils.get(guild.text_channels, name=name): break
            count += 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=name, category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Utworzono zgłoszenie: {ticket_channel.mention}", ephemeral=True)
        
        labels = {"order": "Zamówienie", "help": "Pomoc", "question": "Pytanie", "plugin": "Problem z pluginem", "other": "Inne"}
        embed = discord.Embed(title="Zgłoszenie", description=f"Witaj {interaction.user.mention}!\nOpisz sprawę.\nKategoria: **{labels.get(selected)}**", color=THEME_COLOR)
        
        is_order_ticket = (selected == "order")
        view = TicketControlView(is_order=is_order_ticket)
        await ticket_channel.send(embed=embed, view=view)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# 6. ACCESS VIEW (/nadaj)
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

class AccessView(discord.ui.View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

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
        self.add_view(TicketControlView(is_order=False)) 
        self.add_view(TicketControlView(is_order=True))
        print("🔄 Widoki OK.")
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced: await self.tree.sync(guild=discord.Object(id=GUILD_ID)); self.synced=True
        print(f"✅ Zalogowano: {self.user}")
bot = MyBot()


# --- KOMENDY ---

@bot.tree.command(name="clear", description="[ADMIN] Usuń wiadomości z czatu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(ilosc="Ile wiadomości usunąć?")
async def clear(interaction: discord.Interaction, ilosc: int):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("⛔ Brak uprawnień (Zarządzanie wiadomościami).", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=ilosc)
        await interaction.followup.send(f"🗑️ Usunięto {len(deleted)} wiadomości.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Błąd: {e}", ephemeral=True)

@bot.tree.command(name="konkurs", description="[ADMIN] Rozpocznij giveaway", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nagroda="Co można wygrać?", czas="Ile czasu? (np. 1h, 30m)", ile_osob="Ilu zwycięzców?")
async def konkurs(interaction: discord.Interaction, nagroda: str, czas: str, ile_osob: int = 1):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔ Brak uprawnień.", ephemeral=True)
    seconds = parse_duration_input(czas)
    if not seconds: return await interaction.response.send_message("❌ Zły czas (1h, 30m).", ephemeral=True)
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    ts = int(end_time.timestamp())

    embed = discord.Embed(title="🎉 KONKURS 🎉", description=f"Do wygrania: **{nagroda}**", color=THEME_COLOR)
    embed.add_field(name="⏳ Koniec", value=f"<t:{ts}:R> (<t:{ts}:F>)", inline=False)
    embed.add_field(name="🏆 Zwycięzców", value=str(ile_osob), inline=True)
    
    view = GiveawayView()
    await interaction.response.send_message("Start!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=view)
    await asyncio.sleep(seconds)
    
    parts = list(view.participants)
    if len(parts) < ile_osob: await interaction.channel.send(f"❌ Anulowano: za mało osób ({len(parts)}).")
    else:
        wins = random.sample(parts, ile_osob)
        men = ", ".join([f"<@{u}>" for u in wins])
        e = discord.Embed(title="🎉 WYNIKI 🎉", description=f"Nagroda: **{nagroda}**\n🏆 **{men}**", color=discord.Color.gold())
        await interaction.channel.send(content=men, embed=e)
    
    embed.title="🎉 ZAKOŃCZONY 🎉"; embed.color=discord.Color.dark_gray()
    view.children[0].disabled=True
    await msg.edit(embed=embed, view=view)

@bot.tree.command(name="ustaw_kod", description="[ADMIN] Dodaj kod rabatowy", guild=discord.Object(id=GUILD_ID))
async def ustaw_kod(interaction: discord.Interaction, kod: str, czas: str, procent: int):
    if not interaction.user.guild_permissions.administrator: return
    seconds = parse_duration_input(czas)
    if not seconds: return await interaction.response.send_message("❌ Zły czas", ephemeral=True)
    active_codes[kod] = {"percent": procent, "expires": datetime.datetime.now().timestamp() + seconds}
    e = discord.Embed(title="✅ Kod Rabatowy", color=discord.Color.green())
    e.add_field(name="Kod", value=kod); e.add_field(name="Zniżka", value=f"{procent}%")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="usun_kod", description="[ADMIN] Panel usuwania kodów", guild=discord.Object(id=GUILD_ID))
async def usun_kod(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("⛔ Brak uprawnień.", ephemeral=True)
    if not active_codes: return await interaction.response.send_message("🚫 Brak aktywnych kodów.", ephemeral=True)
    embed = discord.Embed(title="🗑️ Usuwanie kodów", description="Kliknij, aby usunąć.", color=discord.Color.red())
    desc = ""
    for c, d in active_codes.items(): desc += f"• **{c}** ({d['percent']}%) - <t:{int(d['expires'])}:R>\n"
    embed.add_field(name="Lista:", value=desc)
    await interaction.response.send_message(embed=embed, view=DeleteCodeView(), ephemeral=True)

@bot.tree.command(name="nadaj", guild=discord.Object(id=GUILD_ID))
async def nadaj(interaction: discord.Interaction, uzytkownik: discord.Member, zrzut_ekranu: discord.Attachment):
    if not interaction.user.guild_permissions.administrator: return
    e = discord.Embed(title="VoidCode - Weryfikacja", color=THEME_COLOR)
    e.description = f"**Autor:** {uzytkownik.mention}"; e.set_image(url=zrzut_ekranu.url)
    e.set_footer(text=f"ID: {interaction.id}")
    await interaction.channel.send(embed=e, view=AccessView(uzytkownik.id)); await interaction.response.send_message("✅", ephemeral=True)

@bot.tree.command(name="setup_tickety", guild=discord.Object(id=GUILD_ID))
async def setup_ticket(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    desc = """ᴡɪᴛᴀᴊ, ᴘᴏᴛʀᴢᴇʙᴜᴊᴇꜱᴢ ᴘᴏᴍᴏᴄʏ? ᴄʜᴄᴇꜱᴢ ᴄᴏꜱ ᴢᴀᴍᴏᴡɪᴄ?
ᴍᴀꜱᴢ ᴘʏᴛᴀɴɪᴇ ʟᴜʙ ᴘʀᴏʙʟᴇᴍ?
ᴡʏʙɪᴇʀᴢ ᴋᴀᴛᴇɢᴏʀɪᴇ ᴛɪᴄᴋᴇᴛᴜ ᴘᴏᴅ ꜱᴘᴏᴅᴇᴍ.

ᴘʀᴢʏᴘᴏᴍɪɴᴀᴍʏ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴄᴊᴀ ᴍᴀ ꜱᴡᴏᴊᴇ ᴘʀʏᴡᴀᴛɴᴇ ᴢʏᴄɪᴇ ɪ ɴɪᴇ ᴢᴀᴡꜱᴢᴇ ᴅᴏꜱᴛᴀɴɪᴇꜱᴢ ᴏᴅ ʀᴀᴢᴜ ᴏᴅᴘᴏᴡɪᴇᴅᴢ!"""
    e = discord.Embed(title="STWÓRZ ZGŁOSZENIE", description=desc, color=THEME_COLOR)
    await interaction.channel.send(embed=e, view=TicketView()); await interaction.response.send_message("Gotowe", ephemeral=True)

@bot.tree.command(name="setup_weryfikacja", guild=discord.Object(id=GUILD_ID))
async def setup_verify(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    await interaction.channel.send(embed=discord.Embed(title="Weryfikacja", color=THEME_COLOR), view=VerifyView()); await interaction.response.send_message("OK", ephemeral=True)

@bot.tree.command(name="legit", guild=discord.Object(id=GUILD_ID))
async def legit(interaction: discord.Interaction, rola: discord.Role):
    if not interaction.user.guild_permissions.administrator: return
    await interaction.channel.send(embed=discord.Embed(title="Opinia", description=f"Rola: {rola.mention}", color=THEME_COLOR), view=RoleLegitView(rola)); await interaction.response.send_message("OK", ephemeral=True)

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
async def create_embed(interaction: discord.Interaction, tytul: str, tresc: str, kolor: str = "#ffffff", plik: discord.Attachment = None, link_do_obrazka: str = None):
    if not interaction.user.guild_permissions.administrator: return
    try:
        e = discord.Embed(title=tytul, description=tresc.replace("\\n", "\n"), color=int(kolor.replace("#",""),16))
        if link_do_obrazka: e.set_image(url=link_do_obrazka)
        file_to_send = None
        if plik: file_to_send = await plik.to_file()
        await interaction.channel.send(embed=e, file=file_to_send)
        await interaction.response.send_message("OK", ephemeral=True)
    except: await interaction.response.send_message("Błąd", ephemeral=True)

# Admin commands
@bot.tree.command(name="ban", guild=discord.Object(id=GUILD_ID))
async def ban(interaction: discord.Interaction, uzytkownik: discord.Member, powod: str="Brak"):
    if interaction.user.guild_permissions.ban_members: await uzytkownik.ban(reason=powod); await interaction.response.send_message(f"Ban {uzytkownik}")
@bot.tree.command(name="kick", guild=discord.Object(id=GUILD_ID))
async def kick(interaction: discord.Interaction, uzytkownik: discord.Member, powod: str="Brak"):
    if interaction.user.guild_permissions.kick_members: await uzytkownik.kick(reason=powod); await interaction.response.send_message(f"Kick {uzytkownik}")
@bot.tree.command(name="wycisz", guild=discord.Object(id=GUILD_ID))
async def mute(interaction: discord.Interaction, uzytkownik: discord.Member, minuty: int, powod: str="Brak"):
    if interaction.user.guild_permissions.moderate_members: await uzytkownik.timeout(datetime.timedelta(minutes=minuty), reason=powod); await interaction.response.send_message(f"Mute {uzytkownik}")
@bot.tree.command(name="odcisz", guild=discord.Object(id=GUILD_ID))
async def unmute(interaction: discord.Interaction, uzytkownik: discord.Member):
    if interaction.user.guild_permissions.moderate_members: await uzytkownik.timeout(None); await interaction.response.send_message(f"Unmute {uzytkownik}")
@bot.tree.command(name="unban", guild=discord.Object(id=GUILD_ID))
async def unban(interaction: discord.Interaction, user_id: str):
    if interaction.user.guild_permissions.ban_members: 
        try: await interaction.guild.unban(await bot.fetch_user(int(user_id))); await interaction.response.send_message("Unban")
        except: await interaction.response.send_message("Błąd")

# START
keep_alive()
if TOKEN: bot.run(TOKEN)