import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')
    
class DMModal(discord.ui.Modal, title="Send an Embedded DM"):
    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user

        # Title input
        self.title_input = discord.ui.TextInput(
            label="タイトル名 (入れなくてもOK)", 
            placeholder="この埋め込みのタイトルを記入してください", 
            required=False
        )
        self.add_item(self.title_input)

        # Description input
        self.description_input = discord.ui.TextInput(
            label="メッセージ", 
            placeholder="送信したいメッセージを記入してください", 
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.description_input)

        # Color input
        self.color_input = discord.ui.TextInput(
            label="色 (入れなくてもOK)", 
            placeholder="埋め込みの帯の色を**16進数**で入力してください", 
            required=False
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Use default color if no color is provided
        color = self.color_input.value or "0xFFFFFF"
        try:
            color = int(color, 16)
        except ValueError:
            color = 0xFFFFFF

        # Use default title if no title is provided
        title = self.title_input.value or f"**{interaction.user.name} さんからのメッセージ**"

        # Create the embedded message
        embed = discord.Embed(title=title, description=self.description_input.value, color=color)

        # Attempt to send the DM
        try:
            await self.target_user.send(embed=embed)
            await interaction.response.send_message(f"{self.target_user.name}へDMを送信しました。", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("DMの送信に失敗しました。", ephemeral=True)

@bot.tree.command(name="dm_embedded", description="指定したユーザーに埋め込みメッセージでDMを送信します")
@app_commands.describe(
    user="メッセージを送信するユーザー"
)
async def dm_embedded(interaction: discord.Interaction, user: discord.User):
    # Show the modal to the user
    await interaction.response.send_modal(DMModal(target_user=user))

bot.run(os.getenv("TOKEN"))
