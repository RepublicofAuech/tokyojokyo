import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from flask import Flask
import threading
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

app = Flask(__name__)

# Simple route to check if the bot is online
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    # Run the Flask app on port 5000
    app.run(host='0.0.0.0', port=5000)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')
    
class DMModal(discord.ui.Modal, title="Send an Embedded DM"):
    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user

        self.title_input = discord.ui.TextInput(
            label="タイトル名 (入れなくてもOK)", 
            placeholder="この埋め込みのタイトルを記入してください", 
            required=False
        )
        self.add_item(self.title_input)

        self.description_input = discord.ui.TextInput(
            label="メッセージ", 
            placeholder="送信したいメッセージを記入してください", 
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.description_input)

        self.color_input = discord.ui.TextInput(
            label="色 (入れなくてもOK)", 
            placeholder="埋め込みの帯の色を**16進数**で入力してください", 
            required=False
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        color = self.color_input.value or "0xFFFFFF"
        try:
            color = int(color, 16)
        except ValueError:
            color = 0xFFFFFF

        title = self.title_input.value or f"**{interaction.user.name} さんからのメッセージ**"
        embed = discord.Embed(title=title, description=self.description_input.value, color=color)

        try:
            await self.target_user.send(embed=embed)
            await interaction.response.send_message(f"{self.target_user.name}へDMを送信しました。", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("DMの送信に失敗しました。", ephemeral=True)

@bot.tree.command(name="dm_embedded", description="指定したユーザーに埋め込みメッセージでDMを送信します")
@app_commands.describe(user="メッセージを送信するユーザー")
async def dm_embedded(interaction: discord.Interaction, user: discord.User):
    await interaction.response.send_modal(DMModal(target_user=user))

# Run Flask server in a separate thread
threading.Thread(target=run_flask).start()

bot.run(os.getenv("TOKEN"))
