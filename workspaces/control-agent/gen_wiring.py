import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(1, 1, figsize=(16, 10))
ax.set_xlim(0, 16)
ax.set_ylim(0, 10)
ax.axis('off')
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('#f8f9fa')

font = 'Malgun Gothic'

# Title
ax.text(8, 9.5, 'OPT-DPA2024EC-4 배선 연결도 (LCTRL2 교체)',
        ha='center', va='center', fontsize=14, fontweight='bold', color='#1a1a2e', fontfamily=font)

# ===== OPT Controller (center) =====
opt_x, opt_y, opt_w, opt_h = 5.5, 2.5, 5, 5
opt_box = FancyBboxPatch((opt_x, opt_y), opt_w, opt_h,
    boxstyle='round,pad=0.1', linewidth=2, edgecolor='#2c3e50', facecolor='#ecf0f1')
ax.add_patch(opt_box)
ax.text(opt_x + opt_w/2, opt_y + opt_h + 0.25, 'OPT-DPA2024EC-4',
        ha='center', va='bottom', fontsize=11, fontweight='bold', color='#2c3e50', fontfamily=font)
ax.text(opt_x + opt_w/2, opt_y + opt_h + 0.0, 'Multivoltage Digital Controller',
        ha='center', va='top', fontsize=8, color='#7f8c8d')

# Left ports
ports_left = [
    ('전원 (+)', 7.0, '#e74c3c'),
    ('전원 (-)', 6.5, '#2c3e50'),
    ('Trig1 (DI)', 5.5, '#9b59b6'),
    ('COM (GND)', 5.0, '#7f8c8d'),
]
for label, y, color in ports_left:
    ax.plot([opt_x, opt_x - 0.3], [y, y], color=color, lw=2)
    ax.plot(opt_x - 0.3, y, 'o', color=color, markersize=6)
    ax.text(opt_x + 0.15, y, label, ha='left', va='center', fontsize=8, color=color, fontfamily=font)

# Right ports
ports_right = [
    ('CH1+ / CH1-', 7.0, '#e67e22'),
    ('CH2+ / CH2-', 6.3, '#e67e22'),
    ('CH3+ / CH3-', 5.6, '#e67e22'),
    ('DO1 (Open Collector)', 4.9, '#27ae60'),
]
for label, y, color in ports_right:
    ax.plot([opt_x + opt_w, opt_x + opt_w + 0.3], [y, y], color=color, lw=2)
    ax.plot(opt_x + opt_w + 0.3, y, 'o', color=color, markersize=6)
    ax.text(opt_x + opt_w - 0.15, y, label, ha='right', va='center', fontsize=8, color=color, fontfamily=font)

# ===== 24V Power (top-left) =====
pwr_box = FancyBboxPatch((0.5, 7.5), 2.5, 1.2,
    boxstyle='round,pad=0.1', linewidth=1.5, edgecolor='#e74c3c', facecolor='#fdf2f2')
ax.add_patch(pwr_box)
ax.text(1.75, 8.1, '24V 전원 공급', ha='center', va='center', fontsize=9, fontweight='bold', color='#c0392b', fontfamily=font)
ax.text(1.75, 7.75, '(+AV4.0S)', ha='center', va='center', fontsize=8, color='#7f8c8d')

ax.annotate('', xy=(opt_x - 0.3, 7.0), xytext=(3.0, 7.9),
    arrowprops=dict(arrowstyle='->', color='#e74c3c', lw=2))
ax.text(3.6, 7.7, '+24V', ha='center', fontsize=8, color='#e74c3c', fontweight='bold')

ax.annotate('', xy=(opt_x - 0.3, 6.5), xytext=(3.0, 7.65),
    arrowprops=dict(arrowstyle='->', color='#2c3e50', lw=2))
ax.text(3.6, 7.0, 'GND', ha='center', fontsize=8, color='#2c3e50', fontweight='bold')

# ===== TRG1 Board (left-mid) =====
trg_box = FancyBboxPatch((0.5, 3.5), 2.8, 1.6,
    boxstyle='round,pad=0.1', linewidth=1.5, edgecolor='#9b59b6', facecolor='#f5eef8')
ax.add_patch(trg_box)
ax.text(1.9, 4.6, 'TRG1 (TriggerBoard)', ha='center', va='center', fontsize=9, fontweight='bold', color='#7d3c98', fontfamily=font)
ax.text(1.9, 4.2, 'TRG CH3 출력', ha='center', va='center', fontsize=8, color='#7f8c8d', fontfamily=font)
ax.text(1.9, 3.8, 'DC 5~24V (NPN/PNP)', ha='center', va='center', fontsize=7.5, color='#9b59b6')

ax.annotate('', xy=(opt_x - 0.3, 5.5), xytext=(3.3, 4.3),
    arrowprops=dict(arrowstyle='->', color='#9b59b6', lw=2))
ax.text(4.0, 5.2, 'Trig Signal', ha='center', fontsize=8, color='#9b59b6', fontweight='bold')
ax.text(4.0, 4.9, 'COM -> GND', ha='center', fontsize=7.5, color='#9b59b6')

# ===== Lights (right) =====
lights = [
    ('L4 조명 (TopMicro)', 7.2, 'CH1+ / CH1-', 7.0),
    ('L5 조명 (TopMicro)', 5.8, 'CH2+ / CH2-', 6.3),
    ('L6 조명 (TopMicro)', 4.4, 'CH3+ / CH3-', 5.6),
]
for light_label, ly, ch_label, port_y in lights:
    light_box = FancyBboxPatch((12.5, ly), 3.0, 1.0,
        boxstyle='round,pad=0.1', linewidth=1.5, edgecolor='#e67e22', facecolor='#fef9e7')
    ax.add_patch(light_box)
    ax.text(14.0, ly + 0.5, light_label, ha='center', va='center', fontsize=9, fontweight='bold', color='#d35400', fontfamily=font)
    ax.annotate('', xy=(12.5, ly + 0.5), xytext=(opt_x + opt_w + 0.3, port_y),
        arrowprops=dict(arrowstyle='->', color='#e67e22', lw=2))
    ax.text(11.3, (ly + 0.5 + port_y) / 2, ch_label, ha='center', fontsize=8, color='#e67e22', fontweight='bold')

# ===== PC Ethernet (bottom-left) =====
pc_box = FancyBboxPatch((0.5, 1.0), 2.5, 1.2,
    boxstyle='round,pad=0.1', linewidth=1.5, edgecolor='#27ae60', facecolor='#eafaf1')
ax.add_patch(pc_box)
ax.text(1.75, 1.6, 'PC (DEMO SW)', ha='center', va='center', fontsize=9, fontweight='bold', color='#1e8449', fontfamily=font)
ax.text(1.75, 1.2, '100Mbps Ethernet', ha='center', va='center', fontsize=8, color='#7f8c8d')

ax.annotate('', xy=(opt_x + 1.0, opt_y), xytext=(3.0, 1.5),
    arrowprops=dict(arrowstyle='<->', color='#27ae60', lw=1.5, linestyle='dashed'))
ax.text(4.2, 1.9, 'Ethernet\n(채널별 설정/제어)', ha='center', fontsize=8, color='#27ae60', fontfamily=font)

# ===== Notes =====
note_box = FancyBboxPatch((5.5, 0.2), 5.2, 1.8,
    boxstyle='round,pad=0.1', linewidth=1, edgecolor='#f39c12', facecolor='#fffde7')
ax.add_patch(note_box)
ax.text(8.1, 1.8, '주의사항', ha='center', va='center', fontsize=9, fontweight='bold', color='#e67e22', fontfamily=font)
notes = [
    '* 컨트롤러 전원: DC 22~26V (기존 CCS 24V 배선 유지)',
    '* LED 출력: DC 5~48V, 최대 2A/ch (연속), 4A/ch (순간)',
    '* 트리거 극성(NPN/PNP) TRG1 출력 방식 확인 후 배선',
    '* OPT DEMO SW로 채널별 밝기/트리거 딜레이 설정',
]
for i, note in enumerate(notes):
    ax.text(8.1, 1.5 - i * 0.32, note, ha='center', va='center', fontsize=7.5, color='#555', fontfamily=font)

plt.tight_layout()
plt.savefig('C:/MES/wta-agents/workspaces/control-agent/OPT_배선도.png', dpi=150, bbox_inches='tight', facecolor='#f8f9fa')
print('저장 완료')
