import os
from dotenv import load_dotenv
from keep_alive import keep_alive
import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import asyncio

# Ładujemy zmienne (dla testów lokalnych)
load_dotenv()

# --- KONFIGURACJA (UZUPEŁNIJ SWOJE ID!) ---
TOKEN = os.environ.get("TOKEN")

GUILD_ID = 1457834566617403484           # ID Twojego serwera
ROLE_ID_USER = 1457834566617403490       # ID Roli, którą dostaje się po weryfikacji
CHANNEL_WELCOME_ID = 1457834567003144252 # ID kanału powitań
CATEGORY_TICKET_ID = 1457834568080949255 # ID kategorii ticketów
CHANNEL_LEGIT_ID = 1457834567456133207   # ID kanału PUBLICZNEGO z opiniami (ten z licznikiem)

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
                await interaction.response.send_message("❌ Błąd: Nie znaleziono roli weryfikacyjnej (sprawdź ID w kodzie).", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Zła odpowiedź! Spróbuj ponownie.", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zweryfikuj się", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal())

# 2. TICKETY
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
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
            await interaction.response.send_message("❌ Błąd: Nie znaleziono kategorii ticketów (sprawdź ID w kodzie).", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        await interaction.response.send_message(f"✅ Utworzono zgłoszenie: {ticket_channel.mention}", ephemeral=True)
        
        embed = discord.Embed(title="Zgłoszenie", description=f"Witaj {interaction.user.mention}!\nOpisz dokładnie swój problem. Administracja wkrótce odpisze.\n\nWybrana kategoria: **{self.values[0]}**", color=discord.Color.blue())
        await ticket_channel.send(embed=embed)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# 3. LEGIT CHECK (Na Rolę)
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
                 await interaction.response.send_message("❌ Błąd: Nie znaleziono kanału opinii (sprawdź ID w kodzie).", ephemeral=True)
                 return

            embed = discord.Embed(title="✅ NOWY LEGIT CHECK", color=discord.Color.green())
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
            embed.add_field(name="👤 Klient", value=interaction.user.mention, inline=False)
            embed.add_field(name="💸 Cena", value=f"{c}/10", inline=True)
            embed.add_field(name="🚚 Dostawa", value=f"{d}/10", inline=True)
            embed.add_field(name="📞 Obsługa", value=f"{o}/10", inline=True)
            embed.add_field(name="💬 Komentarz", value=self.opis.value, inline=False)
            embed.set_footer(text=f"Ocena końcowa: {srednia}/10 {gwiazdki}")
            
            await public_channel.send(embed=embed)

            # --- LICZNIK W NAZWIE KANAŁU ---
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
                print(f"Licznik kanału error (limit rate?): {e}")

            # Wyłączamy przycisk (skoro to jednorazówka, choć dla roli może to być mylące - jeśli chcesz by każdy z rolą mógł kliknąć RAZ, to inna bajka. 
            # Tutaj wyłączam przycisk po pierwszej opinii, tak jak chciałeś "jednorazowy przycisk")
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
        # Sprawdzamy czy użytkownik ma wymaganą ROLĘ
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
        print("🔄 Załadowano widoki.")

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await self.tree.sync(guild=discord.Object(id=GUILD_ID))
            self.synced = True
        print(f"✅ Zalogowano jako {self.user}!")

bot = MyBot()

# --- KOMENDY ---

# 1. SETUPY
@bot.tree.command(name="setup_weryfikacja", description="[ADMIN] Panel weryfikacji", guild=discord.Object(id=GUILD_ID))
async def setup_verify(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    embed = discord.Embed(title="Weryfikacja", description="Kliknij poniżej, aby uzyskać dostęp.", color=discord.Color.green())
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Gotowe!", ephemeral=True)

@bot.tree.command(name="setup_tickety", description="[ADMIN] Panel ticketów", guild=discord.Object(id=GUILD_ID))
async def setup_ticket(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    embed = discord.Embed(title="STWÓRZ ZGŁOSZENIE", description="Wybierz kategorię poniżej.", color=discord.Color.purple())
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Gotowe!", ephemeral=True)

# 2. LEGIT CHECK (DLA ROLI)
@bot.tree.command(name="legit", description="[ADMIN] Wyślij prośbę o opinię dla posiadaczy danej roli", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(rola="Wybierz rolę (lub wpisz ID), która może wystawić opinię")
async def request_legit(interaction: discord.Interaction, rola: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Tylko admin może prosić o legit check!", ephemeral=True)

    view = RoleLegitView(target_role=rola)
    
    embed = discord.Embed(title="Prośba o opinię", description=f"Dziękujemy za zakupy!\nOsoby z rolą {rola.mention} mogą teraz wystawić opinię klikając przycisk poniżej.", color=discord.Color.gold())
    
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ Utworzono panel opinii dla roli **{rola.name}**.", ephemeral=True)

# 3. TWORZENIE EMBEDA
@bot.tree.command(name="stworz_embed", description="[ADMIN] Tworzy customowy embed z plikiem lub linkiem", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(tytul="Tytuł", tresc="Treść (\\n to nowa linia)", kolor="Hex (np. #ff0000)", plik="Wrzuć obrazek", link_do_obrazka="Lub wklej link")
async def create_embed(interaction: discord.Interaction, tytul: str, tresc: str, kolor: str = "#ffffff", plik: discord.Attachment = None, link_do_obrazka: str = None):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    
    try:
        color_value = int(kolor.replace("#", ""), 16)
        embed = discord.Embed(title=tytul, description=tresc.replace("\\n", "\n"), color=color_value)
        if plik: embed.set_image(url=plik.url)
        elif link_do_obrazka: embed.set_image(url=link_do_obrazka)

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Wysłano embed!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Błąd: {e}", ephemeral=True)

# 4. GIVEAWAY
@bot.tree.command(name="giveaway", description="[ADMIN] Szybki giveaway", guild=discord.Object(id=GUILD_ID))
async def giveaway(interaction: discord.Interaction, nagroda: str, czas_minuty: int):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    
    embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"Nagroda: **{nagroda}**\nCzas: **{czas_minuty} min**\nZareaguj 🎉 aby dołączyć!", color=discord.Color.gold())
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

# 5. MODERACJA
@bot.tree.command(name="ban", description="[ADMIN] Zbanuj użytkownika", guild=discord.Object(id=GUILD_ID))
async def ban(interaction: discord.Interaction, uzytkownik: discord.Member, powod: str = "Brak powodu"):
    if not interaction.user.guild_permissions.ban_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    await uzytkownik.ban(reason=powod)
    await interaction.response.send_message(f"🔨 Zbanowano **{uzytkownik}**. Powód: {powod}")

@bot.tree.command(name="kick", description="[ADMIN] Wyrzuć użytkownika", guild=discord.Object(id=GUILD_ID))
async def kick(interaction: discord.Interaction, uzytkownik: discord.Member, powod: str = "Brak powodu"):
    if not interaction.user.guild_permissions.kick_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    await uzytkownik.kick(reason=powod)
    await interaction.response.send_message(f"🦵 Wyrzucono **{uzytkownik}**. Powód: {powod}")

@bot.tree.command(name="wycisz", description="[ADMIN] Wycisz użytkownika (Timeout)", guild=discord.Object(id=GUILD_ID))
async def mute(interaction: discord.Interaction, uzytkownik: discord.Member, minuty: int, powod: str = "Brak powodu"):
    if not interaction.user.guild_permissions.moderate_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    duration = datetime.timedelta(minutes=minuty)
    await uzytkownik.timeout(duration, reason=powod)
    await interaction.response.send_message(f"🔇 Wyciszono **{uzytkownik}** na {minuty} minut. Powód: {powod}")

@bot.tree.command(name="odcisz", description="[ADMIN] Zdejmij wyciszenie", guild=discord.Object(id=GUILD_ID))
async def unmute(interaction: discord.Interaction, uzytkownik: discord.Member):
    if not interaction.user.guild_permissions.moderate_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    await uzytkownik.timeout(None)
    await interaction.response.send_message(f"🔊 Odciszono **{uzytkownik}**.")

@bot.tree.command(name="unban", description="[ADMIN] Odbanuj użytkownika (podaj ID)", guild=discord.Object(id=GUILD_ID))
async def unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ Odbanowano **{user}**.")
    except:
        await interaction.response.send_message("❌ Nie znaleziono takiego zbanowanego użytkownika.", ephemeral=True)

# --- URUCHOMIENIE ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ BŁĄD: Brak TOKENU w zmiennych środowiskowych!")