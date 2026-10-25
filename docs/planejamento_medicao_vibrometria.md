# Planejamento: medição de vibração com iPhone 17e e Osmo Action 4

**Versão:** 0.1 (rascunho para revisão)
**Data:** 08/10/2026
**Contexto:** campanha de bancada do TCC em vibrometria óptica por fase, com acelerômetro como referência, e aplicativo para PC que apoia a medição.

---

## 1. Objetivo

Medir frequência, amplitude e fase do movimento de uma régua em balanço (aço e polipropileno) a partir de vídeo a 240 fps, usando o método de fase do TCC, e comparar os resultados com:

- a previsão de Euler-Bernoulli (Fase 1);
- o acelerômetro de referência, incluindo o efeito de massa na ponta (Fase 2).

Também se pretende desenvolver um aplicativo para PC que:

- calcule as previsões e verifique a viabilidade do ensaio antes da gravação;
- guie a sessão e padronize os arquivos;
- processe vídeos e acelerômetro e gere tabelas e figuras para o TCC.

**Fora de escopo nesta campanha:** formas modais com vários pontos, medição de campo completo, processamento em tempo real e câmera global shutter (campanha E, somente se chegar a tempo). Esses itens pertencem ao TCC2 e não entram aqui.

---

## 2. Premissas e restrições

### 2.1 Taxa de amostragem

Pela regra de sobreamostragem de 5× Nyquist do TCC1, lida aqui como fs ≥ 10 · f_max, o conteúdo útil deve respeitar f_max ≤ fs / 10:

| Taxa de gravação | Limite de f_max |
|---|---|
| 60 fps | 6 Hz |
| 120 fps | 12 Hz |
| 240 fps | 24 Hz |

Com 240 fps, a bancada (até 20 Hz) atende à regra. A primeira frequência da régua também precisa ficar abaixo de 24 Hz (seção 5).

*Confirmar a interpretação da regra com a definição usada no TCC1.*

### 2.2 Sincronismo e deriva

Um quadro a 240 fps dura 4,17 ms. Em 20 Hz, um atraso de um quadro corresponde a Δφ = 2π · 20 · 0,00417 ≈ 30°.

Uma diferença de 0,1% entre a taxa nominal e a real, acumulada em 10 s, equivale a 10 ms, ou cerca de 72° em 20 Hz.

**Consequência:** amplitude e frequência de cada sinal, calculadas separadamente, não dependem do sincronismo. A fase comparada com o acelerômetro depende. Por isso a fase é métrica secundária e exige sincronismo fracionário (seção 8).

### 2.3 Rolling shutter

O efeito é geométrico. Ele se reduz com ROI pequeno e centrado, porque todas as linhas do ROI são lidas em um intervalo curto. Exposição curta reduz o borrão de movimento, mas não o rolling shutter. Essa distinção deve aparecer no texto do TCC.

### 2.4 Método de fase

O método mede o deslocamento na direção do gradiente da imagem. Para movimento vertical, a régua precisa de bordas horizontais: a borda longa, ou uma linha horizontal de alto contraste colada nela. As marcas de graduação são verticais e quase não contribuem para esse movimento.

Além disso, o módulo do deslocamento deve ser menor que λ₀/2 do filtro usado, para evitar salto de fase.

### 2.5 Geometria

A flexão ocorre na espessura da régua. A câmera deve ficar de lado (vista de perfil), com o eixo óptico perpendicular ao plano de flexão, para que o movimento apareça no plano da imagem.

Com escala de cerca de 0,35 mm/px (câmera a 0,5 m), uma régua de 1 mm de espessura ocupa cerca de 3 px. Por isso o ROI precisa cobrir as duas bordas.

---

## 3. Equipamento

| Item | Especificação | Observações |
|---|---|---|
| **Osmo Action 4** (câmera principal) | Sensor 1/1,3″; 1080p a 240 fps | Já referenciada no TCC. Confirmar 240 fps e o modo FOV linear nesse modo. Desligar RockSteady e HorizonSteady. Registrar o codec. |
| **iPhone 17e** (câmera de comparação) | 1080p a 240 fps (câmera lenta); lente principal 1x | Confirmar 240 fps no aparelho. Travar exposição e foco com toque longo. Usar "Mais compatível" (H.264), se disponível. Sem zoom digital. |
| Acelerômetro | Modelo: [preencher]; taxa ≥ 1 kHz; resposta a partir de ~1 Hz; sensibilidade conforme o certificado | Montagem rígida (parafuso ou cola), com o eixo alinhado ao movimento. Registrar a gravidade. |
| Sinal de comando da bancada | Se disponível | Gravar como referência adicional de fase. |
| Tripé de chão | Independente da bancada | Afastado do excitador. Cabeça e clamp travados. |
| Padrão de escala | Régua ou tabuleiro de 100 mm no plano do movimento | Calibração px → mm. |
| Iluminação | LED em corrente contínua, ou luz forte e constante | Evita cintilação, que aparece como faixas a 240 fps. |
| Sincronismo | Batida seca na bancada + flash de LED visível às câmeras | Marca o início comum. |
| Corpo rígido de teste | Placa ou suporte com dois marcadores verticais | Usado no controle D3 (rolling shutter). |

**Montagem:** câmera de lado, a 0,3 a 0,6 m da régua (distância definida no controle D2). Um referencial fixo na parede ou no chão, para medir o movimento da câmera.

---

## 4. Ajustes de gravação

| Parâmetro | Osmo Action 4 | iPhone 17e |
|---|---|---|
| Resolução e fps | 1080p, 240 fps | 1080p, 240 fps |
| Exposição | Manual com obturador curto, se disponível; senão, AE travado | AE travado (toque longo) |
| Foco | Travado na distância final | Travado (toque longo) |
| Balanço de brancos | Travado | Travado |
| Estabilização | Desligada | Desligada, se houver opção |
| Zoom | Sem zoom digital | Sem zoom digital |
| Codec | Registrar (H.265 ou H.264) | HEVC ou H.264 ("Mais compatível") |
| Duração por ensaio | 10 s de regime + 2 s descartados | Idem |

Se for usar um app de controle manual no iPhone, confirmar que ele mantém 240 fps.

---

## 5. Cálculo prévio (módulo do app)

**Entradas:** material (E, ρ), geometria (L, b, t), massa de ponta e fps de gravação.

**Saídas:**
- f₁, f₂ e f₃ previstos por Euler-Bernoulli;
- verificação de f₁ ≤ fps / 10 (regra 5× Nyquist);
- frequências previstas com as massas de ponta planejadas;
- massa da régua, m_b = ρ · b · t · L.

**Valores típicos (confirmar por catálogo ou medição):**
- Aço inox: E ≈ 200 GPa; ρ ≈ 7850 kg/m³.
- Polipropileno: E ≈ 1,2 a 1,6 GPa; ρ ≈ 900 kg/m³.

**Ordens de grandeza para f₁ (t e L em metros):**
- Aço: f₁ ≈ 815 · t / L²
- Polipropileno: f₁ ≈ 209 · t / L²

Com L = 0,20 m, os limites para 240 fps ficam em: aço, t ≤ 1,2 mm; polipropileno, t ≤ 4,6 mm. Se f₁ passar de 24 Hz, mudar a espessura ou o comprimento, ou não usar essa configuração a 240 fps.

Medir o comprimento efetivo L_eff, da linha de aperto até a ponta. O aperto real não é um engaste perfeito, e a diferença em relação ao modelo deve ser discutida no texto.

---

## 6. Campanhas de ensaio

### Campanha A: vibração livre (Fase 1, comparação com Euler-Bernoulli)

- **Espécimes:** réguas de aço e de polipropileno, com f₁ ≤ 24 Hz (duas geometrias por material, se possível).
- **Procedimento:** deslocar a ponta de 5 a 10 mm e soltar. Gravar de 5 a 10 s.
- **Medidas:** f₁ (pico espectral e ajuste senoidal) e ζ pelo decremento logarítmico entre picos sucessivos.
- **Comparação:** f₁ medido × f₁ de Euler-Bernoulli com L_eff. Erro relativo.
- **Repetições:** 3 por espécime.

### Campanha B: excitação pela bancada (Fase 2, comparação com acelerômetro)

- **Excitação:** senoidal, em 2, 5, 10, 15 e 20 Hz (ajustar à bancada e a f₁).
- **Amplitudes:** 2 níveis dentro do limite da bancada.
- **Repetições:** 3 por condição.
- **Registro:** Osmo e iPhone simultâneos, acelerômetro e, se houver, sinal de comando.
- **Medidas:** amplitude, frequência e fase de cada sinal. O acelerômetro é convertido em deslocamento (seção 8).
- **Total:** 5 × 2 × 3 = 30 sessões, cada uma com as duas câmeras e o acelerômetro.

### Campanha C: efeito de massa (Fase 2)

- **Massas na ponta:** 0, m₁ e m₂ (por exemplo, 5 g e 10 g, conforme a régua).
- **Medidas:** f₁ pelo vídeo e pelo acelerômetro, para cada massa.
- **Comparação:** f₁ medido × f(m) previsto (seção 15).

### Campanha D: controles (antes das campanhas A a C)

- **D1, estabilidade:** câmera e régua paradas por 10 s. O desvio-padrão do deslocamento medido define o limite de resolução, em px e em mm.
- **D2, escala:** régua de 100 mm medida 5 vezes. Erro de escala.
- **D3, rolling shutter:** corpo rígido com dois marcadores verticais, separados por Δy (400 px ou mais, se possível), excitado pela bancada. Como o corpo é rígido, a diferença de fase entre os dois marcadores vem apenas do atraso entre linhas:
  - Δt = Δφ / (2πf)
  - T_read = Δt · H / Δy, com H = altura da imagem em linhas
- **D4, sincronismo:** batida e LED. Verificar o atraso entre vídeo e acelerômetro no início e no fim, para estimar a deriva.
- **D5, taxa real:** ffprobe em cada vídeo. Registrar fps médio, duração e quadros perdidos.

### Campanha E (futura): câmera global shutter

Repetir B e C com a mesma geometria, se a câmera chegar a tempo. Comparar rolling e global shutter em amplitude, fase e faixa de frequência.

---

## 7. Protocolo de sessão

### Checklist antes da gravação

- [ ] Câmera fixa no tripé de chão, de lado, a 0,3 a 0,6 m.
- [ ] Foco, exposição e balanço de brancos travados. Sem zoom.
- [ ] Estabilização desligada.
- [ ] Iluminação em corrente contínua ou constante.
- [ ] Escala de 100 mm no plano do movimento.
- [ ] Acelerômetro montado, alinhado e gravando.
- [ ] Linha de base de 3 s com o sistema parado.

### Sequência de gravação

1. Iniciar os vídeos e o acelerômetro.
2. Linha de base de 3 s.
3. Batida seca e flash de LED (marca de sincronismo).
4. Excitação, com pelo menos 10 s de regime permanente.
5. Parar as gravações e copiar os arquivos sem recodificar.

### Nomeação

`AAAAMMDD_<material>_L<mm>_t<mm>_<f>Hz_A<nível>_r<n>_<câmera>.<ext>`

Exemplo: `20261010_aco_L300_t1_10Hz_A1_r1_osmo.mp4`
Acelerômetro: `20261010_aco_L300_t1_10Hz_A1_r1_acc.csv`

### Arquivo de sessão (YAML)

```yaml
sessao: 20261010_aco_L300_t1_10Hz_A1_r1
especime:
  material: aco_inox
  L_m: 0.300
  b_m: 0.025
  t_m: 0.001
  massa_ponta_kg: 0.0
camera:
  modelo: Osmo Action 4
  resolucao: 1920x1080
  fps_nominal: 240
  fov: linear
  codec: H.265
escala:
  metodo: regua_100mm
  mm_por_px: null
roi:
  x: null
  y: null
  w: null
  h: null
sincronismo:
  impacto_video_s: null
  impacto_acc_s: null
excitacao:
  tipo: senoidal_bancada
  f_Hz: 10
```

---

## 8. Processamento

1. **Ingestão.** Ler os metadados com ffprobe (fps real, número de quadros, pts). Ler os quadros em lotes e recortar o ROI. Não carregar o vídeo inteiro: 2400 quadros de 1080p em tons de cinza ocupam cerca de 5 GB.
2. **Pré-checagem do clipe.**
   - fps real e quadros perdidos;
   - variação do brilho médio do ROI com o alvo parado (picos recorrentes indicam cintilação);
   - foco pela variância do Laplaciano;
   - saturação (fração de pixels em 0 ou 255).
3. **Calibração.** Escala em mm/px com a régua de 100 mm no plano do movimento. Correção de distorção por tabuleiro, se o modo de lente não for linear.
4. **Método de fase (pipeline existente).** Banco de filtros de Gabor, fase por quadro e Δφ em relação a uma referência (média dos primeiros quadros, com a régua parada). Deslocamento u = −Δφ / k₀, com k₀ = 2π/λ₀ do filtro (o sinal depende da convenção e deve ser validado no teste sintético). Média ponderada pela amplitude dentro do ROI.
5. **Referência do movimento da câmera.** Subtrair o deslocamento de um ponto fixo (referencial da parede ou do chão).
6. **Correção de rolling shutter.** t_i = t_quadro + (y_i / H) · T_read, com T_read obtido no controle D3.
7. **Sincronismo.** Atraso inteiro por correlação cruzada do impacto. Atraso fracionário por interpolação do pico da correlação. Verificar a deriva com os eventos de início e fim.
8. **Acelerômetro → deslocamento.** Na frequência de excitação, X = −A / (2πf)². Alternativa: integração no tempo com filtro passa-alta (cerca de 1 Hz) e remoção de offset e de gravidade. Evitar a dupla integração ingênua.
9. **Análise.**
   - Janela de regime permanente (descartar o transitório).
   - Ajuste senoidal por mínimos quadrados na frequência de excitação, obtendo amplitude, fase e offset.
   - Espectro por FFT ou Welch, com janela de Hann.
   - Decremento logarítmico nos ensaios livres.
10. **Métricas.** Erro de frequência (Hz e %), erro de amplitude frente ao acelerômetro (%), erro de fase (°), erro frente a Euler-Bernoulli (%), razão f medida / f prevista com massa e repetibilidade (CV entre repetições).
11. **Saídas.** CSV com séries e resumos; figuras vetoriais em PDF para o LaTeX; tabela em LaTeX (booktabs); JSON com parâmetros e versão do código.

---

## 9. Aplicativo para PC

**Objetivo:** apoiar a medição antes, durante e depois da gravação, e padronizar o processamento.

### MVP

- **R1.** Calcular f₁, f₂ e f₃ previstos e verificar a regra de Nyquist para o fps escolhido.
- **R2.** Criar a sessão (YAML), gerar os nomes de arquivo e exibir o checklist.
- **R3.** Importar vídeos e CSVs. Mostrar metadados e as pré-checagens da seção 8.2.
- **R4.** Calibrar a escala e definir o ROI, com sobreposição visual no vídeo.
- **R5.** Gerar a série de deslocamento pelo método de fase (pipeline existente).
- **R6.** Sincronizar com o acelerômetro e converter aceleração em deslocamento.
- **R7.** Calcular amplitude, frequência, fase, amortecimento e métricas.
- **R8.** Exportar CSV, PDF e tabela LaTeX, com os parâmetros registrados.
- **R9.** Processar em lote uma pasta de sessões.

### Depois (v2)

- Detecção automática do impacto de sincronismo.
- Rastreamento automático da ponta, sem ROI manual.
- Comparação simultânea entre duas câmeras.
- Propagação de incerteza.
- Vários pontos, para formas modais (questão aberta do TCC2).

### Arquitetura (sugestão)

- Python 3.11 ou superior.
- OpenCV para leitura de vídeo e visualização do ROI.
- NumPy e SciPy para filtros, FFT e ajuste.
- pandas ou Polars para tabelas; matplotlib para figuras em PDF; PyYAML para configuração.
- Interface em Streamlit (v1). O núcleo fica separado da interface e pode ser testado sem ela.

### Estrutura de pastas

```
vibrometria/
├── config/                 # sessões (YAML)
├── dados/
│   ├── brutos/             # vídeos e CSVs originais (somente leitura)
│   └── processados/        # séries e resumos
├── relatorios/             # figuras PDF e tabelas LaTeX
├── vibrometria/            # pacote
│   ├── entrada.py          # ffprobe, leitura de quadros, ROI
│   ├── calibracao.py       # escala e distorção
│   ├── fase.py             # integração com o pipeline de Gabor
│   ├── sincronismo.py      # impacto, atraso fracionário, deriva
│   ├── acelerometro.py     # leitura e conversão para deslocamento
│   ├── fisica.py           # Euler-Bernoulli, massa, Nyquist, decremento
│   ├── analise.py          # janelas, ajuste senoidal, FFT, métricas
│   └── relatorio.py        # figuras, CSV, LaTeX
├── app/
│   └── streamlit_app.py
└── testes/
    ├── test_fisica.py
    ├── test_sintetico.py
    └── test_sincronismo.py
```

### Telas

- **Planejar:** material, geometria, massa e fps → f_n previstos, verificação de Nyquist e efeito de massa.
- **Sessão:** checklist, nomes de arquivo e YAML.
- **Processar:** importação, pré-checagens, calibração, ROI com sobreposição e série de deslocamento.
- **Comparar:** acelerômetro, sincronismo, métricas e gráficos.
- **Relatório:** exportação.

---

## 10. Validação

### Testes de software (antes dos dados reais)

- **Vídeo sintético:** textura com deslocamento senoidal conhecido em subpixel, com ruído e borrão. Medir o erro de amplitude e de frequência do método de fase.
- **Rolling shutter sintético:** deslocamento u(t + y · T_read / H). Verificar se a correção recupera T_read.
- **Sincronismo sintético:** atraso fracionário conhecido. Verificar a recuperação.
- **Física:** f_n e efeito de massa contra cálculo analítico.
- **Acelerômetro sintético:** senoide conhecida. Verificar a conversão para deslocamento.

### Validação física

Controles D1 a D5 (seção 6).

---

## 11. Critérios de aceitação (propostos, a validar com o orientador)

| Métrica | Critério proposto |
|---|---|
| Frequência, vídeo × acelerômetro | erro ≤ 1% |
| Amplitude, vídeo × acelerômetro | erro ≤ 10% (meta: ≤ 5%) |
| Fase, vídeo × acelerômetro | erro ≤ 10°, com sincronismo fracionário |
| f₁, vídeo × Euler-Bernoulli | erro ≤ 5%, com L_eff |
| Repetibilidade | CV ≤ 5% |
| Escala (régua de 100 mm) | erro ≤ 1% |
| Ruído (D1) | definir após o controle |

---

## 12. Riscos

| Risco | Efeito | Mitigação |
|---|---|---|
| fps real diferente do nominal, ou variável | Frequência e fase erradas | ffprobe em cada vídeo; checar a deriva com dois eventos |
| Sincronismo de um quadro | Até 30° de erro de fase em 20 Hz | Atraso fracionário; fase como métrica secundária |
| Rolling shutter | Atraso que depende da altura | ROI pequeno; correção com T_read medido (D3) |
| Cintilação de LED | Faixas e picos espúrios | Luz em corrente contínua; checagem na pré-checagem |
| Movimento da câmera | Amplitude errada | Tripé independente; referencial fixo |
| Limite de fase do método | Salto de fase e amplitude errada | Filtro de escala adequada; módulo de u menor que λ₀/2 |
| Aperto diferente de engaste ideal | Desvio em relação a Euler-Bernoulli | Medir L_eff; discutir no texto |
| Compressão (H.265) | Artefatos nas bordas | Iluminação forte; testar H.264; ROI central |
| Integração do acelerômetro | Deriva e amplitude errada | Integração no domínio da frequência; passa-alta |
| f₁ acima de 24 Hz | Viola a regra 5× Nyquist | Cálculo prévio no app; mudar a geometria |
| Régua com poucos pixels de espessura em perfil | Bordas mal resolvidas | ROI cobrindo as duas bordas; ajustar a distância |

---

## 13. Cronograma

Datas a confirmar, porque os prazos foram estendidos. Contagem a partir de 08/10, em dias de trabalho:

- **D0 (hoje):** piloto com as câmeras disponíveis, uma frequência e um espécime. Verificar fps real, rolling shutter e sincronismo.
- **D1 a D2:** núcleo do app (física, entrada, calibração) e testes sintéticos.
- **D3:** método de fase integrado ao pipeline, sincronismo e acelerômetro.
- **D4:** controles D1 a D5.
- **D5 a D6:** campanhas A, B e C.
- **D7:** processamento em lote, revisão e métricas.
- **D8 a D9:** figuras, tabelas e texto de resultados.
- **Campanha E:** somente se a câmera global shutter chegar a tempo.

---

## 14. Decisões em aberto

1. Geometria das réguas de aço e de polipropileno (L e t), conferindo f₁ ≤ 24 Hz.
2. Excitação de toda a campanha pela bancada, ou também vibração livre (campanha A)?
3. Modelo, taxa e formato do CSV do acelerômetro.
4. Distância de gravação e modo de lente (linear ou padrão).
5. Critérios de aceitação, a aprovar com o orientador.
6. Novas datas de entrega parcial e final.
7. Compra da câmera global shutter: decidir após o piloto (D0).
8. Confirmar a interpretação da regra 5× Nyquist do TCC1.

---

## 15. Referência rápida

- **Regra de amostragem:** f_max ≤ fs / 10.
- **Régua em balanço (Euler-Bernoulli):** f_n = (β_n L)² / (2π L²) · t · √(E / 12ρ), com β₁L = 1,8751; β₂L = 4,6941; β₃L = 7,8548.
- **Efeito de massa na ponta:** f(m) = f₁ / √(1 + m / (0,24 · m_b)), com m_b = ρ · b · t · L.
- **Decremento logarítmico:** δ = (1/n) · ln(x₀ / xₙ); ζ = δ / √(4π² + δ²).
- **Fase → deslocamento (método de fase):** u = Δφ / k₀, com k₀ = 2π / λ₀, válido para |u| < λ₀ / 2.
- **Acelerômetro → deslocamento:** |X| = |A| / (2πf)²; fase de X = fase de A − π.
- **Erro de fase por atraso:** Δφ = 2π · f · Δt. Um quadro a 240 fps, em 20 Hz, dá cerca de 30°.
- **Rolling shutter:** Δt = (Δy / H) · T_read.

**Referência do método:** Wadhwa et al. (2013), processamento de movimento em vídeo baseado em fase.
