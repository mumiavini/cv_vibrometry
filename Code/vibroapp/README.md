# Vibrometria — aplicativo desktop

Interface para a campanha de ensaios do TCC: planeja o ensaio, processa o
vídeo pelo método de fase, importa o acelerômetro, sincroniza os dois,
calcula as métricas de validação e exporta tabelas e figuras para o texto.

Toda a lógica de processamento está no pacote `vibrometry` (testável sem a
interface); `vibroapp` é só a interface (PySide6 + pyqtgraph).

## Como abrir

- Duplo clique em `Vibrometria.bat`, na raiz do repositório; ou
- a partir de `Code/`: `..\.venv\Scripts\python -m vibroapp [sessao.vibro.json]`

Dependências: `pip install -r requirements.txt` (PySide6, pyqtgraph, scipy,
pandas, além das que o pipeline já usava).

## Etapas (barra lateral, `Ctrl+1…6`)

| Etapa | O que faz | Planejamento |
|---|---|---|
| **1 Planejar** | f₁, f₂, f₃ de Euler-Bernoulli; efeito de massa na ponta; checagem f₁ ≤ fps/10; espessura máx. e comprimento mín. para o fps; nome padronizado dos arquivos; checklist | R1, R2 |
| **2 Vídeo** | Metadados e fps real; trecho (início/fim); ROIs de medição e de referência arrastáveis sobre o quadro; calibração mm/px traçando um segmento sobre um objeto conhecido; processamento em segundo plano (cancelável); deslocamento, espectro, espectrograma; f, ζ (meia potência e decremento logarítmico), σ (controle D1), erro frente a E-B; aba Qualidade (quadros perdidos, jitter, cintilação, foco, saturação, perda de rastreamento) | R3, R4, R5, R7 |
| **3 Acelerômetro** | CSV/TXT com detecção automática de separador, vírgula decimal e cabeçalho; unidades g, m/s², mm/s², mV/V (sensibilidade); inversão de eixo; deslocamento por integração dupla (frequência ou tempo); f e ζ na janela | R3, R6 |
| **4 Comparar** | Sincronismo por impacto/início da vibração ou correlação (atraso fracionário), deriva de relógio, manual; filtro comum aos dois sinais; comparação em deslocamento ou aceleração; frequência, amplitude, fase, RMS, r, NRMSE, ganho, coerência/FRF; critérios de aceitação editáveis | R6, R7, §11 |
| **5 Lote** | Processa várias sessões (reaproveitando o rastreamento salvo), agrupa repetições `_r<n>` com média, desvio e CV; exporta CSV e LaTeX | R9 |
| **6 Relatório** | Resumo da sessão com os critérios; exporta CSV, JSON (parâmetros + versão do código), tabelas LaTeX (booktabs) e figuras PDF/PNG | R8 |

**Reprodução** (aba da etapa 2): vídeo e gráfico lado a lado. Durante o
processamento, mostra o quadro sendo rastreado e a curva crescendo (10
atualizações/s; custa ~10 % de tempo de processamento). Depois, reproduz em
câmera lenta (1/16× a 1×) com o gráfico desenhado até o instante do quadro.
Pode mostrar só o vídeo ou vídeo × acelerômetro sincronizados, e **Exportar
vídeo…** grava um MP4 (H.264) lado a lado, na velocidade escolhida, para a
apresentação.

Menu `···` → **Gerar dados sintéticos de validação**: cria um vídeo e um
CSV de acelerômetro do *mesmo* movimento, com frequência, amplitude, ζ e
atraso conhecidos, e abre a sessão pronta. Serve para verificar o software
(planejamento §10) antes dos dados reais.

## Sessões

Cada ensaio é um arquivo `*.vibro.json` com todos os parâmetros (caminhos
relativos à pasta da sessão). Ao salvar, o resultado do rastreamento vai
para `*.track.pkl` ao lado; ao reabrir, ele é reaproveitado se o vídeo, as
ROIs e os parâmetros não mudaram (o lote também usa esse cache).

## Convenções

- Interface em tema escuro (preto), definido em `theme.py`. As figuras, as
  tabelas e o vídeo exportados mantêm fundo branco, porque vão para o texto
  impresso e para os slides.
- Tempo da comparação = tempo do vídeo. O acelerômetro é mapeado por
  `t_acel = atraso + (1 + deriva) · t_vídeo`.
- Deslocamento do vídeo em mm se houver escala, senão em px (a amplitude só é
  comparada com o acelerômetro com a escala definida).
- Eixo y da imagem aponta para baixo: se o acelerômetro estiver montado no
  sentido oposto, o sincronismo avisa (polaridade invertida) e basta marcar
  "Inverter sinal" no passo 3.
- O deslocamento integrado do acelerômetro tem efeito de borda nos primeiros
  e últimos ~1/f_hp s do registro (2/f_hp s no método do tempo); a tela de
  comparação avisa se a janela de análise entrar nessa região.

## Verificação

`pytest tests` (a partir de `Code/`) cobre importação do acelerômetro,
integração dupla, sincronismo com atraso fracionário e polaridade, deriva,
ajuste senoidal, rastreamento sub-pixel, Euler-Bernoulli, sessões e o
fluxo completo em vídeo + acelerômetro sintéticos.

Resultados no conjunto sintético padrão (8 Hz, 2 mm, 240 fps, atraso de
0,8374 s):

| Grandeza | Forçado | Livre (ζ = 0,01) |
|---|---|---|
| Atraso recuperado | 0,83739 s | 0,83738 s |
| Erro de frequência, vídeo × acel. | < 0,001 % | 0,013 % |
| Erro de amplitude, vídeo × acel. | −0,69 % | −0,91 % |
| Diferença de fase | 0,00° | −0,24° |
| ζ pelo vídeo | — | 0,0100 |

No vídeo real da régua (`videos/video low res.LRF`, ROIs de
`vibrometry/rois_lrf.json`), o app identifica f₁ = 10,59 Hz, contra
10,58 Hz no TCC.
