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

# --- KONFIGURACJA (UZUPEŁNIJ SWOJE ID!) ---
TOKEN = os.environ.get("TOKEN")

GUILD_ID = 1457834566617403484           
ROLE_ID_USER = 1457834566617403490       # Rola po weryfikacji matematycznej
CHANNEL_WELCOME_ID = 1457834567003144252 
CATEGORY_TICKET_ID = 1457834568080949255 
CHANNEL_LEGIT_ID = 1457834567003144252   

# --- ROLA NADAWANA PRZEZ /NADAJ ---
ROLE_ID_ACCESS = 1457834566617403490     # <--- ZMIEŃ NA ID ROLI KLIENTA/DOSTĘPU

# --- KOLOR ---
THEME_COLOR = discord.Color.from_str("#681CFD")

# --- KLASY I WIDOKI ---

# 1. WERYFIKACJA MATEMATYCZNA
class VerifyModal(discord.ui.Modal, title="Weryfikacja"):
    answer = discord.ui.TextInput(label="Ile to jest 9 + 10?", placeholder="Wpisz wynik cyfrą...")

    async def on_submit(self, interaction: discord.Interaction):
        if self.answer.value.strip() == "19":
            role = interaction.guild.get_role(ROLE_ID_USER)
            if role:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Poprawna odpowiedź! Nadano dostęp.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Błąd: Nie znaleziono roli weryfikacyjnej.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Zła odpowiedź! Spróbuj ponownie.", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zweryfikuj się", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal())

# 2. PANEL NADAWANIA DOSTĘPU (/nadaj) - MODAL ODRZUCENIA
class RejectModal(discord.ui.Modal, title="Powód odrzucenia"):
    reason = discord.ui.TextInput(label="Powód", placeholder="Np. Zły zrzut ekranu, brak subskrypcji...", style=discord.TextStyle.paragraph)

    def __init__(self, view_object, target_user_id):
        super().__init__()
        self.view_object = view_object
        self.target_user_id = target_user_id

    async def on_submit(self, interaction: discord.Interaction):
        # Pobieramy użytkownika
        member = interaction.guild.get_member(self.target_user_id)
        
        # Aktualizujemy wiadomość na kanale (wyłączamy przyciski)
        self.view_object.children[0].disabled = True # Przycisk Nadaj
        self.view_object.children[1].disabled = True # Przycisk Odrzuć
        self.view_object.children[1].label = "Odrzucono"
        await interaction.message.edit(view=self.view_object)
        
        await interaction.response.send_message(f"❌ Odrzucono weryfikację. Powód: {self.reason.value}", ephemeral=True)

        # Wysyłamy info do użytkownika na PV
        if member:
            try:
                embed = discord.Embed(title="❌ Weryfikacja odrzucona", color=discord.Color.red())
                embed.description = f"Twój wniosek o dostęp na serwerze **{interaction.guild.name}** został odrzucony."
                embed.add_field(name="Powód", value=self.reason.value)
                await member.send(embed=embed)
            except:
                pass # Użytkownik ma zablokowane PV

class AccessView(discord.ui.View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="Nadaj dostęp", style=discord.ButtonStyle.success, emoji="✅", custom_id="access_grant")
    async def grant(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TYLKO ADMIN
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("⛔ Ten przycisk jest tylko dla Administratora!", ephemeral=True)

        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        role = guild.get_role(ROLE_ID_ACCESS)

        if member and role:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Nadano dostęp użytkownikowi {member.mention}!", ephemeral=True)
            
            # Edytujemy wiadomość
            button.disabled = True
            button.label = "Dostęp nadany"
            self.children[1].disabled = True 
            await interaction.message.edit(view=self)
            
            # Info PV
            try: await member.send(f"🎉 Twoja weryfikacja na serwerze **{guild.name}** została przyjęta! Nadano dostęp.")
            except: pass
        else:
            await interaction.response.send_message("❌ Błąd: Nie znaleziono użytkownika lub roli.", ephemeral=True)

    @discord.ui.button(label="Brak wymagań", style=discord.ButtonStyle.danger, emoji="❌", custom_id="access_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TYLKO ADMIN
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("⛔ Ten przycisk jest tylko dla Administratora!", ephemeral=True)

        # Otwieramy Modal z powodem
        await interaction.response.send_modal(RejectModal(self, self.target_user_id))

# 3. TICKETY
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zamknij", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_admin = interaction.user.guild_permissions.administrator
        if is_admin:
            await interaction.response.send_message("🗑️ Usuwanie kanału...")
            await asyncio.sleep(2)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("🔒 Dziękujemy za zgłoszenie! Zamykam dostęp.", ephemeral=True)
            await interaction.channel.set_permissions(interaction.user, read_messages=False, send_messages=False)
            embed = discord.Embed(description=f"🔒 Użytkownik {interaction.user.mention} zamknął zgłoszenie.", color=THEME_COLOR)
            await interaction.channel.send(embed=embed)

    @discord.ui.button(label="Przejmij", style=discord.ButtonStyle.success, emoji="✋", custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("⛔ Tylko administracja!", ephemeral=True)
        embed = discord.Embed(description=f"✅ Zgłoszenie przejęte przez: {interaction.user.mention}", color=THEME_COLOR)
        await interaction.channel.send(embed=embed)
        button.disabled = True
        button.label = f"Przejęte przez {interaction.user.display_name}"
        await interaction.message.edit(view=self)

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Zamówienie", description="Chcesz złożyć zamówienie?", emoji="🛒", value="order"),
            discord.SelectOption(label="Pomoc", description="Potrzebujesz naszej pomocy?", emoji="❓", value="help"),
            discord.SelectOption(label="Pytanie", description="Masz do nas pytanie?", emoji="❔", value="question"),
            discord.SelectOption(label="Problem z pluginem", description="Masz problem z naszym pluginem?", emoji="🔌", value="plugin"),
            discord.SelectOption(label="Inne", description="Inna sprawa", emoji="📝", value="other"),
        ]
        super().__init__(placeholder="Wybierz typ zgłoszenia...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(CATEGORY_TICKET_ID)
        if category is None: return await interaction.response.send_message("❌ Błąd kategorii ticketów.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Utworzono zgłoszenie: {ticket_channel.mention}", ephemeral=True)
        
        labels = {"order": "Zamówienie", "help": "Pomoc", "question": "Pytanie", "plugin": "Problem z pluginem", "other": "Inne"}
        embed = discord.Embed(title="Zgłoszenie", description=f"Witaj {interaction.user.mention}!\nOpisz problem. Admin zaraz odpisze.\nKategoria: **{labels.get(self.values[0])}**", color=THEME_COLOR)
        await ticket_channel.send(embed=embed, view=TicketControlView())

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# 4. LEGIT CHECK
class LegitModal(discord.ui.Modal, title="Oceń transakcję"):
    cena = discord.ui.TextInput(label="Ocena ceny (1-10)", placeholder="Np. 10", min_length=1, max_length=2)
    dostawa = discord.ui.TextInput(label="Ocena dostawy (1-10)", placeholder="Np. 9", min_length=1, max_length=2)
    obsluga = discord.ui.TextInput(label="Ocena obsługi (1-10)", placeholder="Np. 10", min_length=1, max_length=2)
    opis = discord.ui.TextInput(label="Twój komentarz", placeholder="...", style=discord.TextStyle.paragraph)

    def __init__(self, view_object):
        super().__init__()
        self.view_object = view_object

    async def on_submit(self, interaction: discord.Interaction):
        try:
            c, d, o = int(self.cena.value), int(self.dostawa.value), int(self.obsluga.value)
            if not (1 <= c <= 10 and 1 <= d <= 10 and 1 <= o <= 10): raise ValueError
            srednia = round((c + d + o) / 3, 1)
            
            public_channel = interaction.guild.get_channel(CHANNEL_LEGIT_ID)
            embed = discord.Embed(title="✅ NOWY LEGIT CHECK", color=THEME_COLOR)
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
            embed.add_field(name="👤 Klient", value=interaction.user.mention, inline=False)
            embed.add_field(name="💸 Cena", value=f"{c}/10", inline=True)
            embed.add_field(name="🚚 Dostawa", value=f"{d}/10", inline=True)
            embed.add_field(name="📞 Obsługa", value=f"{o}/10", inline=True)
            embed.add_field(name="💬 Komentarz", value=self.opis.value, inline=False)
            embed.set_footer(text=f"Ocena: {srednia}/10 {'⭐'*int(srednia)}")
            if public_channel: await public_channel.send(embed=embed)
            
            try:
                if "-" in public_channel.name:
                    p, n = public_channel.name.rsplit("-", 1)
                    if n.isdigit(): await public_channel.edit(name=f"{p}-{int(n)+1}")
            except: pass

            self.view_object.clear_items()
            self.view_object.add_item(discord.ui.Button(label="Opinia wystawiona", disabled=True))
            await interaction.response.edit_message(content="✅ Opinia wystawiona.", view=self.view_object)
        except ValueError: await interaction.response.send_message("❌ Oceny 1-10!", ephemeral=True)

class RoleLegitView(discord.ui.View):
    def __init__(self, target_role):
        super().__init__(timeout=None)
        self.target_role = target_role
    @discord.ui.button(label="Wystaw Opinię", style=discord.ButtonStyle.primary, emoji="⭐")
    async def rate(self, interaction: discord.Interaction, button):
        if self.target_role not in interaction.user.roles: return await interaction.response.send_message("⛔ Brak roli.", ephemeral=True)
        await interaction.response.send_modal(LegitModal(self))

# --- SETUP BOTA ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.synced = False
    async def setup_hook(self):
        self.add_view(VerifyView())
        self.add_view(TicketView())
        self.add_view(TicketControlView())
        print("🔄 Widoki załadowane.")
    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await self.tree.sync(guild=discord.Object(id=GUILD_ID))
            self.synced = True
        print(f"✅ Zalogowano: {self.user}")

bot = MyBot()

# --- KOMENDY ---

@bot.tree.command(name="nadaj", description="[ADMIN] Panel nadawania dostępu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(uzytkownik="Kto ma dostać dostęp?", zrzut_ekranu="Dowód")
async def nadaj(interaction: discord.Interaction, uzytkownik: discord.Member, zrzut_ekranu: discord.Attachment):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("⛔ Brak uprawnień.", ephemeral=True)

    embed = discord.Embed(title="VoidCode - Darmowe Skrypty/Pluginy", color=THEME_COLOR)
    embed.description = f"**Autor:** {uzytkownik.mention}"
    embed.set_image(url=zrzut_ekranu.url)
    embed.set_footer(text=f"ID: {interaction.id} • {datetime.datetime.now().strftime('%H:%M')}")

    view = AccessView(target_user_id=uzytkownik.id)
    
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Panel wysłany.", ephemeral=True)

@bot.tree.command(name="setup_weryfikacja", description="Setup Weryfikacji", guild=discord.Object(id=GUILD_ID))
async def setup_verify(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return 
    embed = discord.Embed(title="Weryfikacja", description="Kliknij poniżej.", color=THEME_COLOR)
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Gotowe", ephemeral=True)

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

@bot.tree.command(name="legit", description="Panel opinii", guild=discord.Object(id=GUILD_ID))
async def legit(interaction: discord.Interaction, rola: discord.Role):
    if not interaction.user.guild_permissions.administrator: return
    await interaction.channel.send(embed=discord.Embed(title="Prośba o opinię", description=f"Osoby z rolą {rola.mention} mogą ocenić.", color=THEME_COLOR), view=RoleLegitView(rola))
    await interaction.response.send_message("Gotowe", ephemeral=True)

@bot.tree.command(name="pv", description="Wyślij PW", guild=discord.Object(id=GUILD_ID))
async def pv(interaction: discord.Interaction, wiadomosc: str, uzytkownik: discord.Member = None, wszyscy: bool = False):
    if not interaction.user.guild_permissions.administrator: return
    await interaction.response.defer(ephemeral=True)
    if wszyscy:
        c=0
        for m in interaction.guild.members:
            if not m.bot:
                try: 
                    await m.send(f"🔔 **Ogłoszenie:**\n\n{wiadomosc}")
                    c+=1
                    await asyncio.sleep(2)
                except: pass
        await interaction.followup.send(f"Wysłano do {c}")
    elif uzytkownik:
        try: 
            await uzytkownik.send(f"🔔 **Wiadomość:**\n\n{wiadomosc}")
            await interaction.followup.send("Wysłano")
        except: await interaction.followup.send("Blokada PW")

@bot.tree.command(name="stworz_embed", description="Kreator embedów", guild=discord.Object(id=GUILD_ID))
async def create_embed(interaction: discord.Interaction, tytul: str, tresc: str, kolor: str = "#ffffff", plik: discord.Attachment = None, link: str = None):
    if not interaction.user.guild_permissions.administrator: return
    try:
        embed = discord.Embed(title=tytul, description=tresc.replace("\\n", "\n"), color=int(kolor.replace("#",""),16))
        if plik: embed.set_image(url=plik.url)
        elif link: embed.set_image(url=link)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Gotowe", ephemeral=True)
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