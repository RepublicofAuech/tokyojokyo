import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import timedelta
import os
from aiohttp import web

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# グローバル変数
setup_done = False
timeout_duration = None  # タイムアウト時間（秒）
message_limit = None  # タイムアウトするメッセージの回数
antispam_enabled_channels = set()
message_counts = {}

# メッセージカウントのクリア
async def clear_message_counts():
    while True:
        await asyncio.sleep(60)  # 1分ごとにリセット
        message_counts.clear()

@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')
    bot.loop.create_task(clear_message_counts())
    await bot.tree.sync()  # コマンドを同期する

# /setup コマンド
@bot.tree.command(name="setup", description="荒らし対策を設定します（管理者限定）")
@app_commands.choices(timeout=[
    app_commands.Choice(name="10分", value=600),
    app_commands.Choice(name="1時間", value=3600),
    app_commands.Choice(name="1日", value=86400)
])
@app_commands.choices(limit=[
    app_commands.Choice(name="3回", value=3),
    app_commands.Choice(name="5回", value=5),
    app_commands.Choice(name="10回", value=10)
])
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction, timeout: app_commands.Choice[int], limit: app_commands.Choice[int]):
    global setup_done, timeout_duration, message_limit
    setup_done = True
    timeout_duration = timeout.value
    message_limit = limit.value
    await interaction.response.send_message(
        f"荒らし対策を設定しました: タイムアウト時間 {timeout.name}, 同じメッセージを連続で送信した回数 {limit.name}",
        ephemeral=True
    )

# /allfilter コマンド
@bot.tree.command(name="allfilter", description="全チャンネルで荒らし対策を有効/無効にします（管理者限定）")
@app_commands.choices(action=[
    app_commands.Choice(name="有効", value="enable"),
    app_commands.Choice(name="無効", value="disable")
])
@app_commands.checks.has_permissions(administrator=True)
async def allfilter(interaction: discord.Interaction, action: app_commands.Choice[str]):
    global setup_done
    if not setup_done:
        await interaction.response.send_message("まず /setup を実行してください。", ephemeral=True)
        return
    if action.value == "enable":
        for channel in interaction.guild.channels:
            if isinstance(channel, discord.TextChannel):
                antispam_enabled_channels.add(channel.id)
        await interaction.response.send_message("荒らし対策を全チャンネルで有効にしました。", ephemeral=True)
    else:
        antispam_enabled_channels.clear()
        await interaction.response.send_message("荒らし対策を全チャンネルで無効にしました。", ephemeral=True)

# /filter コマンド
@bot.tree.command(name="filter", description="特定のチャンネルで荒らし対策を有効/無効にします（管理者限定）")
@app_commands.choices(status=[
    app_commands.Choice(name="有効", value="enable"),
    app_commands.Choice(name="無効", value="disable")
])
@app_commands.checks.has_permissions(administrator=True)
async def filter(interaction: discord.Interaction, channel: discord.TextChannel, status: app_commands.Choice[str]):
    global setup_done
    if not setup_done:
        await interaction.response.send_message("まず /setup を実行してください。", ephemeral=True)
        return
    if status.value == "enable":
        antispam_enabled_channels.add(channel.id)
        await interaction.response.send_message(f"{channel.mention} で荒らし対策を有効にしました。", ephemeral=True)
    else:
        antispam_enabled_channels.discard(channel.id)
        await interaction.response.send_message(f"{channel.mention} で荒らし対策を無効にしました。", ephemeral=True)

# /reset コマンド
@bot.tree.command(name="reset", description="荒らし対策設定をリセットします（管理者限定）")
@app_commands.checks.has_permissions(administrator=True)
async def reset(interaction: discord.Interaction):
    global setup_done, timeout_duration, message_limit, antispam_enabled_channels
    setup_done = False
    timeout_duration = None
    message_limit = None
    antispam_enabled_channels.clear()
    await interaction.response.send_message("荒らし対策設定をリセットしました。", ephemeral=True)

# /look コマンド
@bot.tree.command(name="look", description="現在の荒らし対策設定を確認します")
async def look(interaction: discord.Interaction):
    if not setup_done:
        await interaction.response.send_message("荒らし対策はまだ設定されていません。", ephemeral=True)
        return

    enabled_channels = [f"<#{channel_id}>" for channel_id in antispam_enabled_channels]
    enabled_channels_str = ', '.join(enabled_channels) if enabled_channels else "なし"
    timeout_str = str(timedelta(seconds=timeout_duration))
    limit_str = f"{message_limit}回"

    message = f"タイムアウト時間: {timeout_str}\n同じメッセージを連続で送信した回数: {limit_str}\n有効なチャンネル: {enabled_channels_str}"
    await interaction.response.send_message(message, ephemeral=True)

# メッセージ監視
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.channel.id not in antispam_enabled_channels:
        return

    user_messages = message_counts.get(message.author.id, [])
    user_messages.append(message.content)

    # 連続で同じメッセージが設定された回数以上送信されたかチェック
    if len(user_messages) >= message_limit and all(msg == user_messages[0] for msg in user_messages[-message_limit:]):
        await message.author.timeout(timedelta(seconds=timeout_duration), reason="荒らし対策")
        await message.channel.send(f"{message.author.mention} は同じメッセージを {message_limit} 回連続で送信したため、タイムアウトされました。")
        message_counts.pop(message.author.id, None)
    else:
        message_counts[message.author.id] = user_messages

    await bot.process_commands(message)

# 管理者権限がない場合のエラーハンドラー
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("このコマンドを実行するためには管理者権限が必要です。", ephemeral=True)
    else:
        await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

class VerifyButton(discord.ui.Button):
    def __init__(self, role_id: int):
        super().__init__(label="認証", style=discord.ButtonStyle.primary)
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # 初期レスポンスをすぐに送信
        role = interaction.guild.get_role(self.role_id)
        if role:
            if role in interaction.user.roles:
                await interaction.followup.send("既に認証済みです", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.followup.send("認証が完了しました", ephemeral=True)
        else:
            await interaction.followup.send("ロールが見つかりませんでした", ephemeral=True)

class RoleView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.add_item(VerifyButton(role_id))

# 管理者権限を持つユーザーのみがコマンドを使用できるようにする
@bot.tree.command(name="ninsho", description="指定されたロールIDのロールを付与する認証ボタンを表示します。")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(role_id="付与するロールのID")
async def ninsho(interaction: discord.Interaction, role_id: str):
    try:
        role_id_int = int(role_id)
    except ValueError:
        await interaction.response.send_message("有効な整数のロールIDを入力してください。", ephemeral=True)
        return

    embed = discord.Embed(title="認証システム", description="下のボタンを押して認証を完了してください。")
    await interaction.response.send_message(embed=embed, view=RoleView(role_id_int), ephemeral=False)

# エラーハンドリング：ユーザーに管理者権限がない場合
@ninsho.error
async def ninsho_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("このコマンドを使用するには管理者権限が必要です。", ephemeral=True)

@bot.tree.command(name="google", description="指定したキーワードでGoogle検索を行います。")
@app_commands.describe(query="検索ワード")
async def google_search(interaction: discord.Interaction, query: str):
    # Google検索用のURLを生成
    search_query = query.replace(' ', '+')  # 検索ワードのスペースを + に変換
    search_url = f"https://www.google.com/search?q={search_query}"
    
    # 結果をユーザーに送信
    await interaction.response.send_message(f"Google検索結果: {search_url}")

@bot.tree.command(name="robokasu", description="ロボカス構文を生成します")
@app_commands.describe(say="メッセージ")
async def robokasu(interaction: discord.Interaction, say: str):
    robokaword = say.replace(' ', '+')  # 検索ワードのスペースを + に変換
    result = f"{robokaword}"
    
    # 結果をユーザーに送信
    await interaction.response.send_message(f"# 🤖「{result}」")

async def main():
    # Web server to keep the bot active
    async def handle(request):
        return web.Response(text="Bot is running!")

    app = web.Application()
    app.add_routes([web.get('/', handle)])

    # Get the port from environment or use default 8080
    port = int(os.getenv("PORT", 8080))

    # Run the web server in the background to keep the bot active
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    try:
        # Run the bot
        await bot.start(os.getenv("TOKEN"))
    except Exception as e:
        print(f"Failed to run the bot successfully. Retrying... Error: {e}")
        os.system("kill 1")

# Entry point to run the bot
if __name__ == "__main__":
    asyncio.run(main())
