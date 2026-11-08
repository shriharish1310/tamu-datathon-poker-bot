# Public opponent screen — 2026-11-08

Frozen Starfish `6e5b590bc922f047de670efdd5fd599f7459a75d` was attempted against all 78 pre-pinned repositories. **76 full matches completed: 22 wins, 14 chops, 40 losses; 29/76 official points. Mean profit was −0.361322 BB per paired deal.** No strategy settings changed.

## Method and limits

Each played match used 1,000 duplicated deals, two fresh-process halves, swapped seats, and seed `public-screen-20261108-01`: 152,000 scheduled played hands across 76 matches. Each shard processed opponents sequentially on its own runner. Runtime used the organizer image, one CPU and 4 GiB per bot, read-only files and no external network. Opponents used their pinned public source and declared dependencies with the trusted organizer Dockerfile. These revisions are not confirmed tournament submissions.

This is one seed per opponent, a broad screen rather than a stable ranking. The 76 repositories are not 76 independent strategies: nine have identical complete Python source maps. Source hashes and identities are retained; repository-level official points are reported without treating duplicate policies as independent evidence. A single-seed screen does not quantify performance across future seeds. Nevertheless, the 40 negative official match intervals expose a strategy weakness against this public pool. Prior success against generated opponent families did not establish this strength.

## Reliability

Starfish: zero judge errors, time-bank exhaustion, forfeits, internal fault events or fallback decisions across all 152 halves. Maximum charged half: **3.034210 seconds**. Every post-half Starfish diagnostic was available. Opponents: zero judge errors or forfeits, but one opponent exhausted both half banks. Internal counters for opponents are not generally available.

`AdityaVSM/heads-up-bundle` exhausted both banks (8.000324s and 8.001047s); Starfish won +1.7745 BB/deal. Its result remains an official win, but should not be described as a pure strategic win against a normally functioning opponent. Excluding that match gives **21 wins, 14 chops, 40 losses; 28/75 points; −0.389800 BB/deal**.

## Compatibility exclusions

- `dpro10/datathon-poker`: no usable `agent.py` found. Raw harness status `pending` means entry-point discovery failed, not an unattempted repository.
- `AriCommits/Poker-Bot`: dependency build failed; its FastAPI 0.162.2 pin conflicts with the organizer constraint 0.156.1.

These exclusions are neither wins nor losses. No opponent source or dependency pins were rewritten to make a test pass.

## Largest observed losses

| Opponent | BB/paired deal | Official 95% CI |
|---|---:|---|
| [jbailey117/poker-bot](https://github.com/jbailey117/poker-bot/tree/b65c8f66d2d47646359a86edac47acb9085b611b) | -4.0250 | [-4.8762, -3.1738] |
| [junehwang0930-lang/PokerBot-Team-quad-j](https://github.com/junehwang0930-lang/PokerBot-Team-quad-j/tree/9925feaa9d6342997ceca515fc40d88435138caf) | -3.1895 | [-4.0360, -2.3430] |
| [GrantGallun/plo5-heads-up-bot](https://github.com/GrantGallun/plo5-heads-up-bot/tree/cea5447b405582723dbbdd1af9ba5f549d99cb6f) | -2.5465 | [-3.3462, -1.7468] |
| [oskarexists/heads_up_datathon_2026](https://github.com/oskarexists/heads_up_datathon_2026/tree/527d20a32e91e8b71b36eda6f567d6917e7e847a) | -2.3265 | [-3.1163, -1.5367] |
| [aashrithtutuku02-stack/rangerunner-plo5](https://github.com/aashrithtutuku02-stack/rangerunner-plo5/tree/3aa177f6e9e98ea64cd3482a6b6c5bc35c50a8eb) | -2.2030 | [-2.9725, -1.4335] |
| [650JoshLee (teammate baseline)](https://github.com/650JoshLee) | -2.1265 | [-2.9214, -1.3316] |
| [Utsavdotcom/aura-farmer](https://github.com/Utsavdotcom/aura-farmer/tree/b98a11afb8d940842a5bbfe876ed44956582c40a) | -2.1090 | [-2.8657, -1.3523] |
| [Tanu1007/heads-up-bundle](https://github.com/Tanu1007/heads-up-bundle/tree/2203267f2c1636c0caedac87965de34475469a0f) | -2.0860 | [-2.7987, -1.3733] |

## All played matches

Times are maximum charged half per bot. Every row has zero judge errors and zero forfeits on both sides. `*` marks opponent bank exhaustion.

| Opponent | Starfish result | BB/paired deal | Official 95% CI | Starfish / opponent time |
|---|---|---:|---|---:|
| [650JoshLee (teammate baseline)](https://github.com/650JoshLee) | Loss | -2.1265 | [-2.9214, -1.3316] | 2.408s / 3.131s |
| [aa22222/pkbot](https://github.com/aa22222/pkbot/tree/ec0977e9f2ce0519eea8f97e50d3a7f88a9a7280) | Chop | -0.0225 | [-1.1497, +1.1047] | 2.262s / 4.360s |
| [aashrithtutuku02-stack/rangerunner-plo5](https://github.com/aashrithtutuku02-stack/rangerunner-plo5/tree/3aa177f6e9e98ea64cd3482a6b6c5bc35c50a8eb) | Loss | -2.2030 | [-2.9725, -1.4335] | 2.494s / 1.735s |
| [Aditi6301/rangehunter](https://github.com/Aditi6301/rangehunter/tree/94f8d820c3ed66ea7540e4d9ff5609dab2f5e235) | Loss | -1.9555 | [-2.8597, -1.0513] | 1.367s / 0.902s |
| [AdityaVSM/heads-up-bundle](https://github.com/AdityaVSM/heads-up-bundle/tree/22330246ecb2143b9256204b106473bdfdeaa7a1) | Win* | +1.7745 | [+1.2609, +2.2881] | 2.218s / 8.001s |
| [AiWithAmman/heads-up-bundle-main](https://github.com/AiWithAmman/heads-up-bundle-main/tree/7294d34a065f1ca3d3aed0091f2cea12282ab39b) | Chop | -0.5355 | [-1.3659, +0.2949] | 1.926s / 0.767s |
| [Aiyshwariya/poker-bot](https://github.com/Aiyshwariya/poker-bot/tree/2ba65a83546143c9ea78d50064dcea0b968026a1) | Loss | -0.7050 | [-1.1953, -0.2147] | 2.419s / 2.470s |
| [akshajag/testpokerbot](https://github.com/akshajag/testpokerbot/tree/910ff15c18baf8bf3fa81cdaaf5463bfec135791) | Loss | -0.8830 | [-1.4497, -0.3163] | 2.580s / 1.938s |
| [AllenChirayil/stallion-poker-bot](https://github.com/AllenChirayil/stallion-poker-bot/tree/766a71b2108d3645499c18182981c0c43bb12bc3) | Chop | +0.6170 | [-0.0936, +1.3276] | 2.576s / 7.615s |
| [alterj07/pokerbot](https://github.com/alterj07/pokerbot/tree/bc1f37338bc87e08c4dee9eb527de78e95c7feb5) | Win | +1.3430 | [+0.6753, +2.0107] | 1.450s / 3.804s |
| [ambavane-ayush/testing-poker-bot](https://github.com/ambavane-ayush/testing-poker-bot/tree/0efc9ad6dfc4f9a1bd140848806afb3b4d7a01d0) | Win | +2.4385 | [+1.7146, +3.1624] | 2.096s / 0.001s |
| [andrewv426/timecasters-pokerbot](https://github.com/andrewv426/timecasters-pokerbot/tree/a61a1388f24c6495695d40be5026479266afb818) | Loss | -1.1885 | [-1.8067, -0.5703] | 2.035s / 2.415s |
| [Aniket-tamu/heads-up-bundle](https://github.com/Aniket-tamu/heads-up-bundle/tree/1bd6a32e21aa47544bf352f64332ca0ab4aeda6a) | Loss | -1.5375 | [-2.2248, -0.8502] | 2.446s / 1.896s |
| [ArmaanMediratta/heads-up-bundle](https://github.com/ArmaanMediratta/heads-up-bundle/tree/ed68ed36f0a5e276cb38c1df14884cf8e20aa39a) | Loss | -1.0845 | [-1.6505, -0.5185] | 2.252s / 4.976s |
| [aurora-quantitative-group/Aurora-Poker-Bot](https://github.com/aurora-quantitative-group/Aurora-Poker-Bot/tree/41dcb7624bbc73a08d82913e9c3b34328e73c560) | Loss | -1.0985 | [-1.7409, -0.4561] | 0.928s / 0.001s |
| [awojinrin/xplore-heads-up-poker-bot](https://github.com/awojinrin/xplore-heads-up-poker-bot/tree/20784b7b73ad7b1d6fb5bc4b08c518ff719c184a) | Chop | +0.1365 | [-0.5199, +0.7929] | 2.163s / 4.830s |
| [ayandas-d/JesterBot](https://github.com/ayandas-d/JesterBot/tree/62e435685e756b0d5e48fdacc29908289a545008) | Chop | +0.9880 | [-0.0812, +2.0572] | 1.742s / 2.337s |
| [burnerdrew2-prog/tamu-heads-up-bot](https://github.com/burnerdrew2-prog/tamu-heads-up-bot/tree/03c78d896fad463ef530144bfa8c8cf48a30dab2) | Loss | -1.5140 | [-2.2185, -0.8095] | 2.309s / 3.822s |
| [conorwang8/big-cheese-poker-bot](https://github.com/conorwang8/big-cheese-poker-bot/tree/6d430346b4b6d06d2781a17be55cb8cd451ad723) | Loss | -1.4155 | [-2.1125, -0.7185] | 2.521s / 0.264s |
| [consandrade/pokerbot](https://github.com/consandrade/pokerbot/tree/c83ab6eeb7660a2fd1fae7df224315d41fe985a9) | Win | +0.9205 | [+0.8658, +0.9752] | 1.202s / 0.001s |
| [danjoelsahaya/MoonLily-HeadsUp](https://github.com/danjoelsahaya/MoonLily-HeadsUp/tree/0e884ac7ce4c00bc5d00a0e4adf20e6098db2374) | Win | +4.8300 | [+3.9223, +5.7377] | 0.901s / 0.001s |
| [dchen5267-tamu/heads-up-bundle-main](https://github.com/dchen5267-tamu/heads-up-bundle-main/tree/e6cf616af37397c9b609d627cffe93b4a8193f03) | Win | +2.9630 | [+2.3026, +3.6234] | 2.395s / 3.809s |
| [Dhanush006/ssd-heads-up-poker](https://github.com/Dhanush006/ssd-heads-up-poker/tree/4312bf790e061b431ea97c7ef8a1b3e20b7b7287) | Loss | -1.2200 | [-2.0155, -0.4245] | 2.329s / 3.272s |
| [DiegoAC06/heads-up-green-fn](https://github.com/DiegoAC06/heads-up-green-fn/tree/03d1bfeb689df095db74ea64ad508f79dca5a0be) | Loss | -0.5755 | [-1.0813, -0.0697] | 2.564s / 2.126s |
| [dimi1729/2026_datathon_poker](https://github.com/dimi1729/2026_datathon_poker/tree/37aee33524f901d4400ce48236da7fd1fc8e774e) | Loss | -0.6675 | [-1.1396, -0.1954] | 2.069s / 0.984s |
| [dunlapjack/poker-bot](https://github.com/dunlapjack/poker-bot/tree/33a698e4a34c0490c92be8c5ae86826e6567966d) | Loss | -1.9695 | [-2.6891, -1.2499] | 1.183s / 1.595s |
| [Dushyant-Betala/heads-up-bundle](https://github.com/Dushyant-Betala/heads-up-bundle/tree/ba64c267aa2e8c442e5e5f824539c400faea7a64) | Loss | -1.9755 | [-2.7103, -1.2407] | 1.638s / 0.018s |
| [EmptyDeck/tamu-datathon-2026-heads-up-poker-bot](https://github.com/EmptyDeck/tamu-datathon-2026-heads-up-poker-bot/tree/0a45ceb6b50ef599d2d8c0704805221727338424) | Win | +0.6745 | [+0.1658, +1.1832] | 2.287s / 0.205s |
| [EthereumEthan/plo-heads-up-agent](https://github.com/EthereumEthan/plo-heads-up-agent/tree/b5ff8d3aaa3215f1ff7ac7f1952048619f5a5c98) | Loss | -1.6125 | [-2.3274, -0.8976] | 2.415s / 2.738s |
| [Fargield/td26-poker-bot-v2](https://github.com/Fargield/td26-poker-bot-v2/tree/4ce02282e8e764766d183130d3c44b8af5d2760a) | Loss | -0.5030 | [-0.8693, -0.1367] | 1.815s / 1.944s |
| [GetHub7163/Clanckers-Poker-Bot](https://github.com/GetHub7163/Clanckers-Poker-Bot/tree/a9b2e8ab81acadaf1d97b7897536ce9f63407667) | Win | +0.8180 | [+0.1748, +1.4612] | 2.450s / 1.259s |
| [ghodkeadityarao-tamu/twostack-poker-bot](https://github.com/ghodkeadityarao-tamu/twostack-poker-bot/tree/8f4fbc964c0d2814c36cd3455f25a379e0cf6f66) | Loss | -1.6925 | [-2.3168, -1.0682] | 1.454s / 1.070s |
| [GrantGallun/plo5-heads-up-bot](https://github.com/GrantGallun/plo5-heads-up-bot/tree/cea5447b405582723dbbdd1af9ba5f549d99cb6f) | Loss | -2.5465 | [-3.3462, -1.7468] | 2.365s / 4.294s |
| [harishkumar123tamu/outliers](https://github.com/harishkumar123tamu/outliers/tree/c0fe5ee1d40dc746d738aa2701ea688b4f93add0) | Loss | -1.5825 | [-2.1803, -0.9847] | 1.855s / 2.145s |
| [HarshavardhanRVaricuti/beta-dancers-poker-bot](https://github.com/HarshavardhanRVaricuti/beta-dancers-poker-bot/tree/4f520b4319917e64a5a941d101f087feb033d124) | Loss | -1.9800 | [-2.8200, -1.1400] | 2.313s / 2.553s |
| [imaas-goob/DATATHON](https://github.com/imaas-goob/DATATHON/tree/21cb4a66f511769b60b151228df8ba2986eb7677) | Win | +0.9235 | [+0.8687, +0.9783] | 1.334s / 0.001s |
| [imaas-goob/HeadsUpBot](https://github.com/imaas-goob/HeadsUpBot/tree/c83ab6eeb7660a2fd1fae7df224315d41fe985a9) | Win | +0.9140 | [+0.8591, +0.9689] | 1.223s / 0.001s |
| [itsoporo/datathon-poker-f26-winner](https://github.com/itsoporo/datathon-poker-f26-winner/tree/c83ab6eeb7660a2fd1fae7df224315d41fe985a9) | Win | +0.9265 | [+0.8719, +0.9811] | 1.175s / 0.001s |
| [jait-mukkamalla/tamu-datathon-poker-bot-challenge](https://github.com/jait-mukkamalla/tamu-datathon-poker-bot-challenge/tree/0b4c196f3206f24339251771bc2ea7e5e4084f4e) | Win | +0.9175 | [+0.8627, +0.9723] | 1.190s / 0.001s |
| [jane-vo/tamu-datathon26](https://github.com/jane-vo/tamu-datathon26/tree/ecbe79cc9340b6a355bf246428223e1ddbd80819) | Chop | -0.5405 | [-1.1406, +0.0596] | 1.951s / 2.077s |
| [jbailey117/poker-bot](https://github.com/jbailey117/poker-bot/tree/b65c8f66d2d47646359a86edac47acb9085b611b) | Loss | -4.0250 | [-4.8762, -3.1738] | 2.211s / 3.614s |
| [jiaxinglucasen/poker-bot](https://github.com/jiaxinglucasen/poker-bot/tree/dd2593212855cf79c64c864e72ed889fabab58a6) | Chop | +0.3515 | [-0.5307, +1.2337] | 1.855s / 0.995s |
| [Juan-Sett/HeadsUpBot](https://github.com/Juan-Sett/HeadsUpBot/tree/c210362b3d222142049ab08fdc3cdcc58e40326e) | Loss | -1.1570 | [-1.9061, -0.4079] | 2.004s / 0.600s |
| [junehwang0930-lang/PokerBot-Team-quad-j](https://github.com/junehwang0930-lang/PokerBot-Team-quad-j/tree/9925feaa9d6342997ceca515fc40d88435138caf) | Loss | -3.1895 | [-4.0360, -2.3430] | 1.748s / 1.601s |
| [karammasad/pokerMAKK](https://github.com/karammasad/pokerMAKK/tree/74f698d3f22ee3f29e6e609a4e9c437d52694b9a) | Loss | -1.8185 | [-2.5304, -1.1066] | 2.085s / 1.554s |
| [KrishitaM/ReachForTheMoon--HeadsUp](https://github.com/KrishitaM/ReachForTheMoon--HeadsUp/tree/c83ab6eeb7660a2fd1fae7df224315d41fe985a9) | Win | +0.9255 | [+0.8707, +0.9803] | 1.334s / 0.002s |
| [kswamyget/pokerbot](https://github.com/kswamyget/pokerbot/tree/8d5a5556a5089ba15e24dfcd85b24b93ff69d549) | Win | +3.3435 | [+2.6092, +4.0778] | 2.735s / 2.818s |
| [LaserRyan/Heads-Up-Poker](https://github.com/LaserRyan/Heads-Up-Poker/tree/95a47b59be6718b363844de6269a09a58e3dd812) | Loss | -1.0355 | [-1.6995, -0.3715] | 1.979s / 0.005s |
| [malki-aal/heads-up-bundle](https://github.com/malki-aal/heads-up-bundle/tree/3b94b4233dde531a01ab7fc64a3c740fed38f726) | Loss | -1.5055 | [-2.1998, -0.8112] | 2.432s / 2.312s |
| [Nave3425/poker-bot](https://github.com/Nave3425/poker-bot/tree/252a8f3f96e0217997a6a0a1667d882514dde0cc) | Win | +3.7495 | [+3.0481, +4.4509] | 2.366s / 3.100s |
| [nikhil-inja/heads-up-bundle](https://github.com/nikhil-inja/heads-up-bundle/tree/c83ab6eeb7660a2fd1fae7df224315d41fe985a9) | Win | +0.9220 | [+0.8673, +0.9767] | 1.209s / 0.001s |
| [oskarexists/heads_up_datathon_2026](https://github.com/oskarexists/heads_up_datathon_2026/tree/527d20a32e91e8b71b36eda6f567d6917e7e847a) | Loss | -2.3265 | [-3.1163, -1.5367] | 1.954s / 3.002s |
| [pablois0/heads-up-bundle](https://github.com/pablois0/heads-up-bundle/tree/c83ab6eeb7660a2fd1fae7df224315d41fe985a9) | Win | +0.9150 | [+0.8602, +0.9698] | 1.287s / 0.001s |
| [PayneAM/heads-up-bundle](https://github.com/PayneAM/heads-up-bundle/tree/65b9dfd7a5f9d6eb0f118f5e723c5b840b09f81c) | Loss | -0.7835 | [-1.3198, -0.2472] | 1.580s / 3.438s |
| [Prunuus/heads-up](https://github.com/Prunuus/heads-up/tree/c65ac241e4948248c8384ee399cc6f9551c0f8df) | Loss | -1.0480 | [-1.6540, -0.4420] | 2.157s / 0.110s |
| [RedRojoaka/datathon_2026](https://github.com/RedRojoaka/datathon_2026/tree/10d910e65690beba5e1a5821a22ce2637aec323a) | Chop | +0.2090 | [-0.2800, +0.6980] | 1.547s / 0.786s |
| [returnedlegend/Pokerbot](https://github.com/returnedlegend/Pokerbot/tree/b31f2d17ac5c1fbdca347722944bc7303583046b) | Loss | -1.0635 | [-1.6218, -0.5052] | 2.190s / 0.936s |
| [Risus-Pieces/sooz-pokerbot](https://github.com/Risus-Pieces/sooz-pokerbot/tree/5f7ed054ac4f392b2576ccdf4291e3a07b878f85) | Loss | -1.0805 | [-1.8607, -0.3003] | 2.131s / 0.520s |
| [rtang311627/three-fourths](https://github.com/rtang311627/three-fourths/tree/c83ab6eeb7660a2fd1fae7df224315d41fe985a9) | Win | +0.9210 | [+0.8663, +0.9757] | 1.316s / 0.001s |
| [ruby22-gif/team-blackjack](https://github.com/ruby22-gif/team-blackjack/tree/768cf905d6f23516485ac026cba92ddf9e63c51c) | Chop | -0.3315 | [-1.1132, +0.4502] | 1.411s / 0.685s |
| [SahithReddy-GitHub/poker-bot-tamu-datathon](https://github.com/SahithReddy-GitHub/poker-bot-tamu-datathon/tree/533b6cd844c10cda10d9c827bc0cc676c0634ce0) | Chop | -0.5420 | [-1.2406, +0.1566] | 2.210s / 4.081s |
| [sapyao/heads-up](https://github.com/sapyao/heads-up/tree/82be707748d9d84202b891047686b7c3c4fc4e73) | Chop | -0.0040 | [-0.7394, +0.7314] | 1.381s / 0.050s |
| [shaswat-singh23/datathon-poker](https://github.com/shaswat-singh23/datathon-poker/tree/644305ebf435eadd1c8ad2502745431a74eec014) | Loss | -1.7900 | [-2.4438, -1.1362] | 2.167s / 5.968s |
| [shreynath/PitBossEquity](https://github.com/shreynath/PitBossEquity/tree/6b2921de93674e8600659540e307df5894b9e259) | Loss | -1.2570 | [-1.9374, -0.5766] | 2.788s / 4.641s |
| [snr2753423/heads-up-bot](https://github.com/snr2753423/heads-up-bot/tree/1fefd42f8cf893f3bc0d9aadc926017ae4956e6c) | Win | +0.9120 | [+0.3088, +1.5152] | 2.333s / 2.575s |
| [Solomon1493/heads-up-bot](https://github.com/Solomon1493/heads-up-bot/tree/3e86d7d2b608f8aedf0ab4e41494d0147290839d) | Loss | -1.2140 | [-1.7830, -0.6450] | 1.741s / 1.727s |
| [someoneisarhino/tamu-datathon26](https://github.com/someoneisarhino/tamu-datathon26/tree/f81031252a30ea76c6c1e12fcea1b275e1ff8212) | Win | +1.3845 | [+0.7474, +2.0216] | 1.977s / 2.201s |
| [Sploofie/f26-datathon-poker-bot](https://github.com/Sploofie/f26-datathon-poker-bot/tree/e1c4d9bda85f517aa94fd47f2ee36f6d84457214) | Win | +0.9175 | [+0.8628, +0.9722] | 1.222s / 0.001s |
| [Tanu1007/heads-up-bundle](https://github.com/Tanu1007/heads-up-bundle/tree/2203267f2c1636c0caedac87965de34475469a0f) | Loss | -2.0860 | [-2.7987, -1.3733] | 1.784s / 0.016s |
| [The007Programmer/AEY-TDatathon](https://github.com/The007Programmer/AEY-TDatathon/tree/7ee8b402ff4626129e10892b0514253a168ccbf2) | Loss | -1.3655 | [-2.1283, -0.6027] | 3.034s / 2.168s |
| [thmfirst50-jpg/PokerBot](https://github.com/thmfirst50-jpg/PokerBot/tree/431f53bc8629453ebc309d74d2d196f0752b7c16) | Chop | -0.6415 | [-1.3054, +0.0224] | 2.179s / 1.961s |
| [ujjwalbana07/poker-bot](https://github.com/ujjwalbana07/poker-bot/tree/3a6a3c5104ba01b9abf4c78b43e2350dc2f6b586) | Chop | -0.2235 | [-0.8243, +0.3773] | 1.970s / 3.026s |
| [Utsavdotcom/aura-farmer](https://github.com/Utsavdotcom/aura-farmer/tree/b98a11afb8d940842a5bbfe876ed44956582c40a) | Loss | -2.1090 | [-2.8657, -1.3523] | 2.212s / 0.849s |
| [vignesh-nagarajan-vn/ShortStack-Poker](https://github.com/vignesh-nagarajan-vn/ShortStack-Poker/tree/7ab25b614ac294d259fc9332352ca8d381f679e3) | Loss | -1.6095 | [-2.2223, -0.9967] | 1.354s / 2.013s |
| [zeyad-commits/heads_up](https://github.com/zeyad-commits/heads_up/tree/33eb79e16af039227cc1d0c4c6a568aeccc93487) | Win | +2.4385 | [+1.7146, +3.1624] | 2.300s / 0.001s |
| [zuhairrr07/Poker-Bot](https://github.com/zuhairrr07/Poker-Bot/tree/16965ebd30dbc7a79bcbcc6f695b4c65fceaf727) | Chop | -0.2935 | [-1.0010, +0.4140] | 3.006s / 3.026s |

## Evidence and reproduction

[Successful Actions run](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42503687734), harness commit `b0eb6349bdbf54c064f8f1a6f39635d69192a52b`. All seven downloaded artifact ZIP SHA-256 hashes match GitHub metadata. Raw archives are retained locally under `reports/public-archives`; GitHub artifacts expire on December 8, 2026. [Evidence manifest](PUBLIC_OPPONENTS_EVIDENCE.json) records artifact hashes, expiry dates, opponent source hashes and local Docker image IDs; these IDs identify local builds rather than registry-published images. [Audited results](PUBLIC_OPPONENTS_RESULTS.json) retain identities, per-half stats, available diagnostics and raw half/match hashes.

```bash
gh run download 42503687734 --pattern "public-opponents-*" --dir reports/public-downloaded
python tools/audit_public_results.py reports/public-downloaded
```

The audit recomputes paired profits and 95% intervals directly from raw halves, checks seats, seeds, source revisions, zero-sum payouts and forfeit overrides, and agrees with all 76 official results. The initial run `42503421910` failed its self-check because the unprivileged judge could not write its output volume. It played no external matches. The successful run changed the judge helper UID to match the host output owner and preserved all failed-attempt logs.

## Decision

Do not present frozen Starfish as competitive with the stronger public bots based on its generated-opponent results. Keep it frozen as an audited baseline and reliability fallback; no upgrade was selected or tested here. The user-reported caller-conditioned candidate `3e36f20` is outside this screen. The submitted/default branch, release tags and strategy remain unchanged. No submission was made by this benchmark.
