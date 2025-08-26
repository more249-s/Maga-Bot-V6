
import os, asyncio, httpx, datetime as dt
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands, tasks

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID","0"))
REVIEW_CHANNEL_ID = int(os.getenv("REVIEW_CHANNEL_ID","0"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID","0"))
API_BASE = os.getenv("API_BASE","http://localhost:8000")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)
tree = bot.tree

def is_admin(member: discord.Member):
    return any(r.id == ADMIN_ROLE_ID for r in member.roles) or member.guild_permissions.administrator

async def api(method, path, **kwargs):
    async with httpx.AsyncClient(timeout=20) as client:
        return await client.request(method, f"{API_BASE}{path}", **kwargs)

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    if not overdue_loop.is_running():
        overdue_loop.start()
    print(f"Logged in as {bot.user}")

# ========== أوامر الإدارة ==========
@tree.command(name="اضف_عمل", description="إنشاء عمل + رول بنفس الاسم", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(العمل="اسم العمل (مثال: Naruto)")
async def add_work(interaction: discord.Interaction, العمل: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Admins only", ephemeral=True)
    guild = interaction.guild
    # Create discord role without permissions
    role = discord.utils.get(guild.roles, name=العمل)
    if not role:
        role = await guild.create_role(name=العمل, permissions=discord.Permissions.none(), reason="Work role")
    # Save in backend
    r = await api("POST","/api/works", json={"name": العمل}, headers={"Authorization": f"Bearer {interaction.user.id}"})
    if r.status_code >= 300:
        txt = r.text
    else:
        txt = "تم إنشاء العمل + الرول بنجاح"
    await interaction.response.send_message(f"{txt}\nالرول: {role.mention}", ephemeral=True)

@tree.command(name="وزع", description="توزيع مهمة بسيطة", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(عضو="العضو", رول_العمل="الرول باسم العمل", رقم_الفصل="رقم الفصل")
async def assign_simple(interaction: discord.Interaction, عضو: discord.Member, رول_العمل: discord.Role, رقم_الفصل: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("Admins only", ephemeral=True)
    # ensure member has the role
    if رول_العمل not in عضو.roles:
        await عضو.add_roles(رول_العمل, reason="Work assignment")
    # find/create backend work
    # get works
    r = await api("GET","/api/works", headers={"Authorization": f"Bearer {interaction.user.id}"})
    work = None
    if r.status_code==200:
        for w in r.json():
            if w["name"].lower() == رول_العمل.name.lower():
                work = w; break
    if not work:
        # create
        cr = await api("POST","/api/works", json={"name": رول_العمل.name}, headers={"Authorization": f"Bearer {interaction.user.id}"})
        work = cr.json()
    # create task
    t = await api("POST","/api/tasks", json={"work_id": work["id"], "chapter_number": رقم_الفصل, "assignee_discord_id": str(عضو.id)}, headers={"Authorization": f"Bearer {interaction.user.id}"})
    if t.status_code>=300:
        return await interaction.response.send_message(f"API error: {t.text}", ephemeral=True)
    await interaction.response.send_message(f"📌 تم توزيع الفصل {رقم_الفصل} على {عضو.mention} في {رول_العمل.mention}", ephemeral=False)

@tree.command(name="استلام", description="تأكيد استلام المهمة وبدء العد التنازلي (24h)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(مهمة="ID المهمة" )
async def start_task(interaction: discord.Interaction, مهمة: int):
    # member only on his task
    r = await api("POST", f"/api/tasks/{مهمة}/start", headers={"Authorization": f"Bearer {interaction.user.id}"})
    if r.status_code>=300:
        return await interaction.response.send_message(f"{r.text}", ephemeral=True)
    await interaction.response.send_message("✅ تم الاستلام، عندك 24 ساعة لتسليم العمل.", ephemeral=True)

@tree.command(name="تسليم", description="تسليم فصل باللينك أو الملف", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(مهمة="ID المهمة", نوع_العمل="ترجمة أو تحرير", رفع_على_درايف="رفع الملف على Google Drive؟", رابط="لينك (اختياري)")
async def submit_task(interaction: discord.Interaction, مهمة: int, نوع_العمل: str, رفع_على_درايف: bool=False, رابط: str=None, ملف: discord.Attachment=None):
    form = {"type": نوع_العمل, "upload_to_drive": str(رفع_على_درايف).lower(), "link": رابط}
    files=None
    if ملف:
        data = await ملف.read()
        files = {"file": (ملف.filename, data, ملف.content_type or "application/octet-stream")}
    r = await api("POST", f"/api/tasks/{مهمة}/submit", headers={"Authorization": f"Bearer {interaction.user.id}"}, data=form, files=files)
    if r.status_code>=300:
        return await interaction.response.send_message(f"{r.text}", ephemeral=True)
    # send to review channel
    ch = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
    payload = r.json()
    emb = discord.Embed(title="مراجعة فصل", description=f"مهمة #{مهمة}", color=0x2ecc71)
    emb.add_field(name="صاحب المهمة", value=interaction.user.mention)
    emb.add_field(name="النوع", value=نوع_العمل)
    if payload.get("link"): emb.add_field(name="الرابط", value=payload["link"], inline=False)
    view = ReviewView(task_id=مهمة, user_id=interaction.user.id)
    await ch.send(embed=emb, view=view)
    await interaction.response.send_message("📬 تم التسليم وتم إرساله للمراجعة.", ephemeral=True)

# ========== مراجعة بالأزرار ==========
class ReviewView(discord.ui.View):
    def __init__(self, task_id: int, user_id: int):
        super().__init__(timeout=None)
        self.task_id = task_id
        self.user_id = user_id

    @discord.ui.button(label="✅ قبول", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Admins only", ephemeral=True)
        r = await api("POST", f"/api/tasks/{self.task_id}/review", json={"action": "accept"}, headers={"Authorization": f"Bearer {interaction.user.id}"})
        await interaction.response.send_message("✅ تم قبول الفصل وإضافة النقاط/الرصيد.", ephemeral=True)

    @discord.ui.button(label="❌ رفض", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Admins only", ephemeral=True)
        r = await api("POST", f"/api/tasks/{self.task_id}/review", json={"action": "reject", "reason": "Rejected"}, headers={"Authorization": f"Bearer {interaction.user.id}"})
        await interaction.response.send_message("❌ تم الرفض.", ephemeral=True)

    @discord.ui.button(label="🔄 طلب تعديل", style=discord.ButtonStyle.secondary, custom_id="changes_btn")
    async def changes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Admins only", ephemeral=True)
        r = await api("POST", f"/api/tasks/{self.task_id}/review", json={"action": "changes", "reason": "Please fix"}, headers={"Authorization": f"Bearer {interaction.user.id}"})
        await interaction.response.send_message("🔄 تم إرسال طلب التعديل للعضو.", ephemeral=True)

# ========== AI ==========
@tree.command(name="ai", description="مساعد ذكي للنصوص والصور", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(نص="السؤال أو النص", لغة="لغة الرد (ar/en)")
async def ai_cmd(interaction: discord.Interaction, نص: str=None, لغة: str="ar", صورة: discord.Attachment=None):
    if صورة:
        data = await صورة.read()
        files = {"file": (صورة.filename, data, صورة.content_type or "image/png")}
        r = await api("POST","/api/ai/image", files=files, params={"lang": لغة}, headers={"Authorization": f"Bearer {interaction.user.id}"})
        out = r.json().get("text","(no text)")
    else:
        r = await api("POST","/api/ai/chat", json={"prompt": نص or "", "lang": لغة}, headers={"Authorization": f"Bearer {interaction.user.id}"})
        out = r.json().get("reply","(no reply)")
    await interaction.response.send_message(out[:1900], ephemeral=True)

# ========== مراقبة المتأخرين (24h) ==========
@tasks.loop(minutes=int(os.getenv("CHECK_INTERVAL_MINUTES","30")))
async def overdue_loop():
    try:
        # Backend will mark overdue; here we can DM members & notify admins as needed in real deployment.
        await api("GET","/api/tasks")  # trigger connectivity
    except Exception:
        pass

bot.run(TOKEN)
