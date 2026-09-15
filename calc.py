import math

cx, cy = 600, 420
r = 340
w, h = 220, 150 # card dims

nodes = ["Connect", "Discovery", "Strategy", "Modernization", "Summary"]
# Angles: -90, -18, 54, 126, 198
angles = [-90, -18, 54, 126, 198]

for i, name in enumerate(nodes):
    rad = math.radians(angles[i])
    x = cx + r * math.cos(rad) - w/2
    y = cy + r * math.sin(rad) - h/2
    print(f"{name}: left {x/1200*100}%, top {y/800*100}%")
