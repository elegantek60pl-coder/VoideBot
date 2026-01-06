import os
from dotenv import load_dotenv
from keep_alive import keep_alive
import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import asyncio

# Ładujemy zmienne (przydatne przy testach na komputerze)
load_dotenv()

# --- KONFIGURACJA ---
# TERAZ TOKEN JEST POBIERANY Z SYSTEMU - NIE WPISUJ GO TU!
TOKEN = os.environ.get("TOKEN")

# Ustawienia ID (Twoje)
GUILD_ID = 1457834566617403484  
ROLE_ID_USER = 1457834566617403490  
CHANNEL_WELCOME_ID = 1457834567003144252 
CATEGORY_TICKET_ID = 1457834568080949255 

# --- WIDOKI (VIEWS) ---
class VerifyModal(discord.ui.Modal, title="Weryfikacja"):
    answer = discord.ui.TextInput(label="Ile to jest 9 + 10?", placeholder="Wpisz wynik cyfrą...")

    async def on_submit(self, interaction: discord.Interaction):
        # Sprawdzamy czy odpowiedź to 19
        if self.answer.value.strip() == "19":
            role = interaction.guild.get_role(ROLE_ID_USER)
            if role:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Poprawna odpowiedź! Nadano dostęp.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Błąd: Nie znaleziono roli (sprawdź ID w kodzie).", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Zła odpowiedź! Spróbuj ponownie.", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zweryfikuj się", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal())

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Pomoc", description="Potrzebujesz naszej pomocy?", emoji="❓", value="help"),
            discord.SelectOption(label="Pytanie", description="Masz do nas pytanie?", emoji="❔", value="question"),
            discord.SelectOption(label="Problem z pluginem", description="Masz problem z naszym pluginem?", emoji="🔌", value="plugin"),
            discord.SelectOption(label="Inne", description="Inna sprawa", emoji="📝", value="other"),
        ]
        super().__init__(placeholder="Wybierz typ zgłoszenia...", min_values=1, max_values=1, custom_id="ticket_select")

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


# --- SETUP BOTA ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.synced = False

    async def setup_hook(self):
        self.add_view(VerifyView())
        self.add_view(TicketView())
        print("🔄 Załadowano widoki (VerifyView, TicketView)")

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await self.tree.sync(guild=discord.Object(id=GUILD_ID))
            self.synced = True
        print(f"✅ Zalogowano jako {self.user}!")
        print("Bot jest gotowy do działania.")

bot = MyBot()

# --- 1. POWITANIA ---
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(CHANNEL_WELCOME_ID)
    if channel:
        guild = member.guild
        embed = discord.Embed(
            description=f"👋 {member.mention} dołączył(-a) na nasz serwer **{guild.name}**. Jest aktualnie {guild.member_count} użytkowników.",
            color=discord.Color.from_rgb(147, 112, 219)
        )
        await channel.send(embed=embed)

# --- KOMENDY ---
@bot.tree.command(name="setup_weryfikacja", description="Wstawia panel weryfikacji", guild=discord.Object(id=GUILD_ID))
async def setup_verify(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Tylko admin może to zrobić!", ephemeral=True)
        
    embed = discord.Embed(title="Weryfikacja", description="Kliknij przycisk poniżej i rozwiąż proste równanie, aby uzyskać dostęp do serwera.", color=discord.Color.green())
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Panel weryfikacji wysłany!", ephemeral=True)

@bot.tree.command(name="setup_tickety", description="Wstawia panel ticketów", guild=discord.Object(id=GUILD_ID))
async def setup_ticket(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Tylko admin może to zrobić!", ephemeral=True)

    embed = discord.Embed(title="STWÓRZ ZGŁOSZENIE!", description="Administracja ma maksymalnie **48 godzin** na sprawdzenie Twojego zgłoszenia.\nProsimy o cierpliwość.", color=discord.Color.purple())
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/4128/4128176.png") 
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Panel ticketów wysłany!", ephemeral=True)

@bot.tree.command(name="stworz_embed", description="Tworzy customowy embed", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(tytul="Tytuł embeda", tresc="Treść embeda (użyj \\n dla nowej linii)", kolor="Kolor hex (np. #ff0000)", obrazek="Link do obrazka (opcjonalnie)")
async def create_embed(interaction: discord.Interaction, tytul: str, tresc: str, kolor: str = "#ffffff", obrazek: str = None):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
        
    try:
        color_value = int(kolor.replace("#", ""), 16)
        embed = discord.Embed(title=tytul, description=tresc.replace("\\n", "\n"), color=color_value)
        if obrazek:
            embed.set_image(url=obrazek)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Wysłano embed!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Błąd: {e}", ephemeral=True)

@bot.tree.command(name="giveaway", description="Rozpoczyna szybki giveaway", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nagroda="Co jest do wygrania?", czas_minuty="Czas trwania w minutach")
async def giveaway(interaction: discord.Interaction, nagroda: str, czas_minuty: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)

    embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"Do wygrania: **{nagroda}**\nCzas: **{czas_minuty} minut**!\n\nZareaguj 🎉 aby dołączyć!", color=discord.Color.gold())
    await interaction.response.send_message("Rozpoczęto giveaway!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")

    await asyncio.sleep(czas_minuty * 60)

    msg = await interaction.channel.fetch_message(msg.id)
    users = []
    async for user in msg.reactions[0].users():
        if not user.bot:
            users.append(user)

    if users:
        winner = random.choice(users)
        win_embed = discord.Embed(title="🎉 KONIEC GIVEAWAYU 🎉", description=f"Zwycięzca: {winner.mention}\nNagroda: **{nagroda}**", color=discord.Color.green())
        await interaction.channel.send(content=f"{winner.mention}", embed=win_embed)
    else:
        await interaction.channel.send("Nikt nie wziął udziału w giveawayu :(")

# --- URUCHOMIENIE ---
keep_alive() # Odpalamy serwer dla Rendera

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ BŁĄD: Nie znaleziono tokenu w zmiennych środowiskowych! Ustaw go w panelu Render.")