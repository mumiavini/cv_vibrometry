# Acelerômetro — mola k₁ = 1500 N/m (B&K 4507 001 + LAN-XI 3160-A-4/2, PULSE LabShop)

**Os dados desta pasta são DIGITALIZADOS** a partir de uma foto da tela do PULSE
(`Book/Images/pulse_curva_acelerometro_foto.jpg`); não são uma exportação do software.
No texto do TCC devem ser identificados como "curva digitalizada a partir da tela do
PULSE". A leitura direta do cursor (7,600 Hz) é dado medido.

| Arquivo | Conteúdo |
|---|---|
| `acc_k1_envelope_digitalizado.csv` | envoltória do sinal no tempo, 1,30–14,0 s: `t_s, upper_ms2, lower_ms2, half_p2p_ms2` (`half_p2p` = (máx − mín)/2 em janela de 0,4 s) |
| `acc_k1_espectro_digitalizado.csv` | espectro 0–10 Hz, passo 0,05 Hz: `f_hz, amplitude_ms2, origem`; só o pico (7,2–8,1 Hz) e o bump DC (< 0,3 Hz) têm valor, o resto é indistinguível do eixo (< 0,01 m/s²); o bin de 7,60 Hz vem da leitura do cursor (1,07 m/s²) |
| `acc_k1_metadata.json` | proveniência, leituras diretas, calibração e resultados |
| `curva_acelerometro_tempo_k1.csv` | série `tempo_s, aceleracao_m_s2` a 200 Hz (0,03–19,345 s) extraída da curva do PULSE por outra digitalização. **Não é uma forma de onda**: 97 % das diferenças sucessivas alternam de sinal e ≈ 47 % da energia está em 50–100 Hz (os extremos de cada traço vertical do gráfico, alternados), então não deve ser integrada nem usada para fase/forma de onda. Serve só pela envoltória (concorda com `acc_k1_envelope_digitalizado.csv` a poucos %) e pela frequência (componente de 6,5–9 Hz em 7,606 Hz) |

**Leitura direta do software (medida):** cursor do espectro `X = 7,600 Hz`, `Y = 1,07 m/s²`;
cursor do tempo `X = 2,188 s`, `Y = −354 mm/s²`; gravação de 15/10/2026 20:48:57.

**Configuração inferida (confirmar no setup do PULSE):** FFT com 200 linhas, banda 10 Hz,
T = 20 s ⇒ Δf = 0,05 Hz e fs = 25,6 Hz (512 amostras/bloco), ≈ 3,4 amostras por ciclo de 7,6 Hz.

## Qualidade da digitalização (validada contra os cursores do próprio PULSE)

| Quantidade | Digitalizado | Referência | Erro |
|---|---|---|---|
| frequência do pico do espectro | 7,62 Hz | 7,600 Hz | +0,02 Hz (+0,26 %) |
| cursor de frequência relido | 7,619 Hz | 7,600 Hz | +0,019 Hz |
| cursor de tempo relido | 2,189 s | 2,188 s | +0,001 s |
| cursor de amplitude relido | 1,073 m/s² | 1,07 m/s² | +0,003 m/s² |
| ζ pelo decaimento da envolvente (2,5–9 s, R² = 0,998) | 0,0072–0,0079 | — | — |

A foto tem só ≈ 3,6 px por amostra, então forma de onda amostra a amostra **não** é
recuperável; a comparação com o vídeo é feita por envoltória, frequência e decaimento
(`Code/vibrometry/reference.py`). Substituir por exportação do PULSE se ela se tornar possível.
