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
ROLE_ID_USER = 1457834566617403490       
CHANNEL_WELCOME_ID = 1457834567003144252 
CATEGORY_TICKET_ID = 1457834568080949255 
CHANNEL_LEGIT_ID = 1457834567003144252   

# --- TWÓJ KOLOR GŁÓWNY (#681CFD) ---
THEME_COLOR = discord.Color.from_str("#681CFD")

# --- KLASY I WIDOKI ---

# 1. WERYFIKACJA
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

# 2. TICKETY - Panel Sterowania
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
            await interaction.response.send_message("🔒 Dziękujemy za zgłoszenie! Zamykam dostęp do tego kanału.", ephemeral=True)
            await interaction.channel.set_permissions(interaction.user, read_messages=False, send_messages=False)
            
            embed = discord.Embed(description=f"🔒 Użytkownik {interaction.user.mention} zamknął zgłoszenie. Kanał czeka na usunięcie przez Admina.", color=THEME_COLOR)
            await interaction.channel.send(embed=embed)

    @discord.ui.button(label="Przejmij", style=discord.ButtonStyle.success, emoji="✋", custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("⛔ Tylko administracja może przejmować tickety!", ephemeral=True)

        embed = discord.Embed(description=f"✅ Zgłoszenie zostało przejęte przez: {interaction.user.mention}", color=THEME_COLOR)
        await interaction.channel.send(embed=embed)
        button.disabled = True
        button.label = f"Przejęte przez {interaction.user.display_name}"
        await interaction.message.edit(view=self)

# 2. TICKETY - Wybór kategorii
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
        
        if category is None:
            await interaction.response.send_message("❌ Błąd: Nie znaleziono kategorii ticketów.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        await interaction.response.send_message(f"✅ Utworzono zgłoszenie: {ticket_channel.mention}", ephemeral=True)
        
        labels = {
            "order": "Zamówienie",
            "help": "Pomoc",
            "question": "Pytanie",
            "plugin": "Problem z pluginem",
            "other": "Inne"
        }
        selected_label = labels.get(self.values[0], "Nieznana")

        embed = discord.Embed(title="Zgłoszenie", description=f"Witaj {interaction.user.mention}!\nOpisz dokładnie swój problem. Administracja wkrótce odpisze.\n\nWybrana kategoria: **{selected_label}**", color=THEME_COLOR)
        await ticket_channel.send(embed=embed, view=TicketControlView())

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# 3. LEGIT CHECK
class LegitModal(discord.ui.Modal, title="Oceń transakcję"):
    cena = discord.ui.TextInput(label="Ocena ceny (1-10)", placeholder="Np. 10", min_length=1, max_length=2)
    dostawa = discord.ui.TextInput(label="Ocena dostawy (1-10)", placeholder="Np. 9", min_length=1, max_length=2)
    obsluga = discord.ui.TextInput(label="Ocena obsługi (1-10)", placeholder="Np. 10", min_length=1, max_length=2)
    opis = discord.ui.TextInput(label="Twój komentarz", placeholder="Napisz co sądzisz o zamówieniu...", style=discord.TextStyle.paragraph)

    def __init__(self, view_object):
        super().__init__()
        self.view_object = view_object

    async def on_submit(self, interaction: discord.Interaction):
        try:
            c = int(self.cena.value)
            d = int(self.dostawa.value)
            o = int(self.obsluga.value)
            
            if not (1 <= c <= 10 and 1 <= d <= 10 and 1 <= o <= 10):
                raise ValueError("Ocena poza skalą")

            srednia = round((c + d + o) / 3, 1)
            gwiazdki = "⭐" * int(srednia)

            public_channel = interaction.guild.get_channel(CHANNEL_LEGIT_ID)
            if not public_channel:
                 await interaction.response.send_message("❌ Błąd: Nie znaleziono kanału opinii.", ephemeral=True)
                 return

            embed = discord.Embed(title="✅ NOWY LEGIT CHECK", color=THEME_COLOR)
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
            embed.add_field(name="👤 Klient", value=interaction.user.mention, inline=False)
            embed.add_field(name="💸 Cena", value=f"{c}/10", inline=True)
            embed.add_field(name="🚚 Dostawa", value=f"{d}/10", inline=True)
            embed.add_field(name="📞 Obsługa", value=f"{o}/10", inline=True)
            embed.add_field(name="💬 Komentarz", value=self.opis.value, inline=False)
            embed.set_footer(text=f"Ocena końcowa: {srednia}/10 {gwiazdki}")
            
            await public_channel.send(embed=embed)

            try:
                current_name = public_channel.name
                if "-" in current_name:
                    parts = current_name.rsplit("-", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        prefix = parts[0]
                        number = int(parts[1])
                        new_number = number + 1
                        new_name = f"{prefix}-{new_number}"
                        await public_channel.edit(name=new_name)
            except Exception as e:
                print(f"Licznik kanału error: {e}")

            self.view_object.clear_items()
            self.view_object.add_item(discord.ui.Button(label="Opinia wystawiona", style=discord.ButtonStyle.grey, disabled=True))
            await interaction.response.edit_message(content="✅ Opinia została wystawiona.", view=self.view_object)

        except ValueError:
            await interaction.response.send_message("❌ Błąd: Oceny muszą być liczbami od 1 do 10!", ephemeral=True)

class RoleLegitView(discord.ui.View):
    def __init__(self, target_role):
        super().__init__(timeout=None)
        self.target_role = target_role

    @discord.ui.button(label="Wystaw Opinię", style=discord.ButtonStyle.primary, emoji="⭐")
    async def rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.target_role not in interaction.user.roles:
            return await interaction.response.send_message(f"⛔ Aby wystawić opinię, musisz posiadać rolę: **{self.target_role.name}**!", ephemeral=True)
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
        print("🔄 Załadowano widoki.")

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await self.tree.sync(guild=discord.Object(id=GUILD_ID))
            self.synced = True
        print(f"✅ Zalogowano jako {self.user}!")

bot = MyBot()

# --- KOMENDY ---

@bot.tree.command(name="setup_weryfikacja", description="[ADMIN] Panel weryfikacji", guild=discord.Object(id=GUILD_ID))
async def setup_verify(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    embed = discord.Embed(title="Weryfikacja", description="Kliknij poniżej, aby uzyskać dostęp.", color=THEME_COLOR)
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Gotowe!", ephemeral=True)

@bot.tree.command(name="setup_tickety", description="[ADMIN] Panel ticketów", guild=discord.Object(id=GUILD_ID))
async def setup_ticket(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    
    opis_panelu = """ᴡɪᴛᴀᴊ, ᴘᴏᴛʀᴢᴇʙᴜᴊᴇꜱᴢ ᴘᴏᴍᴏᴄʏ? ᴄʜᴄᴇꜱᴢ ᴄᴏꜱ ᴢᴀᴍᴏᴡɪᴄ?
ᴍᴀꜱᴢ ᴘʏᴛᴀɴɪᴇ ʟᴜʙ ᴘʀᴏʙʟᴇᴍ?
ᴡʏʙɪᴇʀᴢ ᴋᴀᴛᴇɢᴏʀɪᴇ ᴛɪᴄᴋᴇᴛᴜ ᴘᴏᴅ ꜱᴘᴏᴅᴇᴍ.

ᴘʀᴢʏᴘᴏᴍɪɴᴀᴍʏ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴄᴊᴀ ᴍᴀ ꜱᴡᴏᴊᴇ ᴘʀʏᴡᴀᴛɴᴇ ᴢʏᴄɪᴇ ɪ ɴɪᴇ ᴢᴀᴡꜱᴢᴇ ᴅᴏꜱᴛᴀɴɪᴇꜱᴢ ᴏᴅ ʀᴀᴢᴜ ᴏᴅᴘᴏᴡɪᴇᴅᴢ!"""

    embed = discord.Embed(title="STWÓRZ ZGŁOSZENIE", description=opis_panelu, color=THEME_COLOR)
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Gotowe!", ephemeral=True)

@bot.tree.command(name="pv", description="[ADMIN] Wyślij wiadomość DM", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(wiadomosc="Treść wiadomości", uzytkownik="Konkretny użytkownik", wszyscy="Do wszystkich? (True/False)")
async def pv(interaction: discord.Interaction, wiadomosc: str, uzytkownik: discord.Member = None, wszyscy: bool = False):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)

    if wszyscy:
        count = 0
        members = interaction.guild.members
        await interaction.followup.send(f"⏳ Rozpoczynam wysyłanie do {len(members)} osób...")
        for member in members:
            if not member.bot:
                try:
                    await member.send(f"🔔 **Ogłoszenie:**\n\n{wiadomosc}")
                    count += 1
                    await asyncio.sleep(2) 
                except: pass
        await interaction.followup.send(f"✅ Wysłano do {count} osób.")

    elif uzytkownik:
        try:
            await uzytkownik.send(f"🔔 **Wiadomość:**\n\n{wiadomosc}")
            await interaction.followup.send(f"✅ Wysłano do {uzytkownik.mention}.")
        except:
            await interaction.followup.send(f"❌ Użytkownik ma zablokowane PW.")
    else:
        await interaction.followup.send("❌ Wybierz użytkownika lub opcję 'wszyscy'.")

@bot.tree.command(name="legit", description="[ADMIN] Panel opinii dla roli", guild=discord.Object(id=GUILD_ID))
async def request_legit(interaction: discord.Interaction, rola: discord.Role):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    view = RoleLegitView(target_role=rola)
    embed = discord.Embed(title="Prośba o opinię", description=f"Dziękujemy za zakupy!\nOsoby z rolą {rola.mention} mogą teraz wystawić opinię klikając przycisk poniżej.", color=THEME_COLOR)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ Utworzono panel dla {rola.name}.", ephemeral=True)

@bot.tree.command(name="stworz_embed", description="[ADMIN] Tworzy customowy embed", guild=discord.Object(id=GUILD_ID))
async def create_embed(interaction: discord.Interaction, tytul: str, tresc: str, kolor: str = "#ffffff", plik: discord.Attachment = None, link_do_obrazka: str = None):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    try:
        # Ten jeden embed zachowuje kolor wybrany przez Ciebie
        color_value = int(kolor.replace("#", ""), 16)
        embed = discord.Embed(title=tytul, description=tresc.replace("\\n", "\n"), color=color_value)
        
        # Poprawka do obrazków
        if plik:
            embed.set_image(url=plik.url)
        elif link_do_obrazka:
            # Sprawdzamy czy to link http
            if link_do_obrazka.startswith("http"):
                embed.set_image(url=link_do_obrazka)
            else:
                await interaction.channel.send("⚠️ Ostrzeżenie: Link do obrazka musi zaczynać się od http/https.")
        
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Wysłano embed!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Błąd: {e}", ephemeral=True)

@bot.tree.command(name="giveaway", description="[ADMIN] Giveaway", guild=discord.Object(id=GUILD_ID))
async def giveaway(interaction: discord.Interaction, nagroda: str, czas_minuty: int):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"Nagroda: **{nagroda}**\nCzas: **{czas_minuty} min**\nZareaguj 🎉 aby dołączyć!", color=THEME_COLOR)
    await interaction.response.send_message("Start!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    await asyncio.sleep(czas_minuty * 60)
    msg = await interaction.channel.fetch_message(msg.id)
    users = []
    async for user in msg.reactions[0].users():
        if not user.bot: users.append(user)
    if users:
        winner = random.choice(users)
        await interaction.channel.send(f"🎉 Wygrał: {winner.mention}! Nagroda: **{nagroda}**")
    else:
        await interaction.channel.send("Nikt nie wygrał :(")

@bot.tree.command(name="ban", description="[ADMIN] Ban", guild=discord.Object(id=GUILD_ID))
async def ban(interaction: discord.Interaction, uzytkownik: discord.Member, powod: str = "Brak powodu"):
    if not interaction.user.guild_permissions.ban_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    await uzytkownik.ban(reason=powod)
    await interaction.response.send_message(f"🔨 Zbanowano **{uzytkownik}**. Powód: {powod}")

@bot.tree.command(name="kick", description="[ADMIN] Kick", guild=discord.Object(id=GUILD_ID))
async def kick(interaction: discord.Interaction, uzytkownik: discord.Member, powod: str = "Brak powodu"):
    if not interaction.user.guild_permissions.kick_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    await uzytkownik.kick(reason=powod)
    await interaction.response.send_message(f"🦵 Wyrzucono **{uzytkownik}**. Powód: {powod}")

@bot.tree.command(name="wycisz", description="[ADMIN] Timeout", guild=discord.Object(id=GUILD_ID))
async def mute(interaction: discord.Interaction, uzytkownik: discord.Member, minuty: int, powod: str = "Brak powodu"):
    if not interaction.user.guild_permissions.moderate_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    duration = datetime.timedelta(minutes=minuty)
    await uzytkownik.timeout(duration, reason=powod)
    await interaction.response.send_message(f"🔇 Wyciszono **{uzytkownik}** na {minuty} minut. Powód: {powod}")

@bot.tree.command(name="odcisz", description="[ADMIN] Un-timeout", guild=discord.Object(id=GUILD_ID))
async def unmute(interaction: discord.Interaction, uzytkownik: discord.Member):
    if not interaction.user.guild_permissions.moderate_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    await uzytkownik.timeout(None)
    await interaction.response.send_message(f"🔊 Odciszono **{uzytkownik}**.")

@bot.tree.command(name="unban", description="[ADMIN] Unban", guild=discord.Object(id=GUILD_ID))
async def unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ Odbanowano **{user}**.")
    except:
        await interaction.response.send_message("❌ Nie znaleziono użytkownika.", ephemeral=True)

# --- URUCHOMIENIE ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ BŁĄD: Brak TOKENU w zmiennych środowiskowych!")