# Created by lcapy-tk V0.94.dev0
; nodes={1@(11, 5), 0@(13, 0), 3@(6, 6), 4@(6, 4), 8@(13, 5), 12@(13, 1.5), 5@(3, 6), 11@(3, 0), 2@(6, 2.5), 6@(6, 0.5), 7@(11, 2.5)}
E1 1 0 opamp 3 4 A 0 0; right
W3 1 8; right
P1 8 12; down=1.5, v=V_o
V1 5 11; down=2
W7 11 0; down=0, sground
W1 5 3; right=1.5
W2 4 2; down=0.75, scale=0.75
R1 2 6; down
R2 2 7; right=2.5
W5 7 1; up=1.25
W4 6 0; down=0.25, scale=0.25, sground
W6 12 0; down=0.75, scale=0.75, sground
; draw_nodes=connections, label_nodes=none, style=american, voltage_dir=RP, label_style=value
