# Roteiro de laboratório — bancada barra + mola

Objetivo da visita: **fechar o que não fecha hoje** (k × massa da mola, amortecimento vídeo × PULSE, tomadas
diferentes) e **coletar os dados que faltam para o TCC**. Tudo aqui tem um motivo; o item entre parênteses diz
qual dúvida ele resolve. Prioridade: **P1** obrigatório · **P2** muito desejável · **P3** se der tempo.

## 0. Levar

- balança com resolução de 0,1 g (ou melhor) e massas conhecidas / garrafas pesadas na própria balança
- paquímetro, trena, régua de 100 mm (ou fita métrica fixada no plano da barra), fita e marcador
- tripé (de chão, independente da bancada), iPhone 17e carregado, espaço livre (240 fps ocupa ≈ 0,7 GB por minuto)
- luz LED em corrente contínua (ou luz forte constante; evitar lâmpada fluorescente)
- martelinho/objeto para o impacto de sincronismo; segunda fonte de luz tipo lanterna de celular (flash de LED)
- notebook com PULSE LabShop e o aplicativo (`Vibrometria.bat`); pen drive
- esta folha impressa ou aberta, e uma caneta

## 1. Medir a mola e as ferragens (P1) — resolve "k de catálogo × massa efetiva"

Só com 7,6 Hz não dá para separar k de massa (`issues.md`/`TODO.md`). Meça os dois diretamente.

**1.1 Pesar, uma a uma, com a balança zerada** (anote o modelo e a resolução da balança):

| Peça | Massa [g] |
|---|---|
| mola k₁ (sozinha) | |
| mola k₂ (sozinha) | |
| parafuso que atravessa a barra | |
| porcas + arruelas (todas, as que ficam na montagem) | |
| gancho / elo / haste de ligação mola → parafuso | |
| acelerômetro B&K 4507 001 (sem o cabo) | |
| cabo do acelerômetro: trecho que fica pendurado (≈) | |
| a barra (conferir ≈ 660 g) | |
| conjunto cilindro/dial do lado da junta, se for solto (ou só anotar o que é) | |

> No app, a massa efetiva da mola é **⅓ da massa da mola** + as ferragens. Preencha na etapa 1 os campos
> "m mola [g]" e "ferragens [g]" — **não** como uma massa pontual única (hoje a sessão tem uma massa
> "ferragem" de 383 g a 632 mm; se esse número for o peso total da mola + ferragens, o app está contando a
> mola inteira em vez de ⅓).

**1.2 Medir k estaticamente (a que mais pesa).** Retire a mola da barra e pendure-a **no mesmo suporte/gancho
superior** onde ela trabalha (inclui a flexibilidade da fixação). Pendure massas conhecidas no gancho de baixo:

| Massa pendurada [kg] (pesada) | Comprimento da mola [mm] (paquímetro/trena, mesma referência) |
|---|---|
| 0 (só ferragens) | |
| ≈ 0,5 | |
| ≈ 1,0 | |
| ≈ 1,5 | |
| ≈ 2,0 | |

Faça **subindo e descendo** a carga (histerese/atrito) e repita para **k₁ e k₂**. O app ajusta k = Δ(m·g)/Δx
(inclinação); espere dentro de ±5 % do catálogo se estiver certo.

**1.3 Checagem dinâmica da massa efetiva (P2).** Com uma massa conhecida de ≈ 1 kg pendurada na mola, puxe um
pouco e solte; filme a 240 fps (ou conte 20 ciclos com cronômetro): f = √(k / (m + m_mola/3)) / 2π. Isso
confirma o fator ⅓ e o k estático.

## 2. Geometria da montagem (P1) — resolve "L efetivo / raiz"

Meça **a partir do centro do eixo do mancal** (não da borda da barra):

| Grandeza | Valor |
|---|---|
| distância centro do mancal → ponta da barra | |
| distância centro do mancal → furo/parafuso da mola | (esperado 632 mm) |
| distância centro do mancal → centro do acelerômetro | (esperado 300 mm) |
| largura b e espessura h da barra (3 pontos cada, paquímetro) | |
| há folga/atrito no mancal? (balançar a barra sem a mola) | sim / não |
| o que é o cilindro/dial do lado da junta, está preso à barra? | |
| altura da barra em repouso (nivelada?) e comprimento da mola em repouso | |

Fotografe de lado e de cima, com a trena aparecendo.

## 3. Preparar o ensaio (P1)

1. **Marcas na barra** (fita ou marcador, bem visíveis na câmera): em x = 0 (centro do mancal), 300 (acelerômetro),
   632 (parafuso) e na ponta. Servem de ROI de alto contraste **e** de escala (evita o erro 100 mm × 720 mm).
2. **Câmera:** tripé fixo, vista de lado, eixo óptico perpendicular ao plano de flexão, foco/exposição/balanço de
   branco travados (toque longo), 1080p a **240 fps** (slow motion), sem zoom, estabilização desligada, luz
   constante. Enquadre a barra inteira **e uma região de parede com textura** (referência fixa).
3. Anote a distância câmera–barra e **não mexa mais no tripé** durante a sessão (se mexer, recalibre).
4. **PULSE: aquisição com taxa alta** (P1). A taxa de 25,6 Hz (banda 10 Hz) deixa só ~3 amostras por ciclo:
   configure a **banda para ≥ 100 Hz** (fs ≥ 256 Hz, ≥ 30 amostras por ciclo de 7,6 Hz) e duração ≥ 20 s.
   Anote: banda/linhas/duração, sensibilidade do acelerômetro e ganho, e o nome do projeto/medição.
5. **Exportar:** tente salvar o sinal no tempo do próprio PULSE (menus *File → Export / Save As* ou botão direito no
   gráfico → copiar/exportar; formatos ASCII/Excel/MAT/WAV). Se conseguir, pegue **o arquivo** e anote o caminho.
   Se não conseguir, tire **screenshot do PC** (não foto da tela) com o gráfico em tela cheia e o cursor no pico.
6. Acelerômetro colado/preso com o eixo na direção do movimento (vertical); cabo preso para não encostar na barra
   nem em nada que amorteça.

## 4. Gravações (P1) — mesma liberação, vídeo e PULSE ao mesmo tempo

**Procedimento de cada tomada:**
1. Iniciar PULSE e o vídeo (anote a **hora do relógio do PC e do celular** — foto dos dois relógios no início do dia).
2. **3 s de linha de base** com tudo parado.
3. **Impacto de sincronismo:** batida seca com o martelinho na barra **junto de um flash** da lanterna visível na
   câmera (marca no PULSE = pico de aceleração; no vídeo = quadro do flash/movimento).
4. **Liberar do mesmo ponto:** puxe a ponta da barra até uma marca fixa (mesma amplitude em todas as tomadas, p. ex.
   amplitude de ≈ 8 mm no acelerômetro como antes) e solte sem empurrar.
5. Deixar decair **≥ 20 s** (até o sinal sumir). Parar as duas gravações.
6. Nomear já no local: `AAAAMMDD_al_L720_k<1|2>_<cond>_r<n>_iphone.mov` e `..._acc.<ext>`; anote na tabela.

| # | Mola | Acelerômetro | Lâmina do amortecedor | Rep. | Arquivo vídeo | Arquivo PULSE | f_n (cursor) [Hz] | Obs. |
|---|---|---|---|---|---|---|---|---|
| 1 | k₁ | sim | fora do óleo | 1 | | | | |
| 2 | k₁ | sim | fora do óleo | 2 | | | | |
| 3 | k₁ | sim | fora do óleo | 3 | | | | |
| 4 | k₂ | sim | fora do óleo | 1 | | | | |
| 5 | k₂ | sim | fora do óleo | 2 | | | | |
| 6 | k₂ | sim | fora do óleo | 3 | | | | |
| 7 | k₁ | **não** (só vídeo) | fora | 1 | | — | — | mass loading (P2) |
| 8 | k₁ | **não** | fora | 2 | | — | — | |
| 9 | k₁ | **não** | fora | 3 | | — | — | |
| 10 | k₁ | sim | **dentro do óleo** | 1 | | | | amortecimento (P2) |
| 11 | k₁ | sim | dentro do óleo | 2 | | | | |

Em cada tomada anote o f_n do cursor do PULSE e se a **lâmina do amortecedor** e a **pré-carga da mola**
estavam como nas outras. **Fotografe o amortecedor** (lâmina dentro/fora) antes de cada bloco.

> Por quê: as tomadas 1–6 dão f_n e ζ na **mesma** liberação (compara vídeo × PULSE de verdade e mostra a
> repetibilidade); 7–9 medem o efeito do acelerômetro (esperado ≈ −0,1 a −0,4 %, perto da resolução); 10–11 mostram
> se o amortecedor explica a diferença de ζ (vídeo ≈ 0,001 × PULSE ≈ 0,007).

## 5. Controles rápidos (P2)

- **D1, estabilidade (≈ 2 min):** filme a barra parada por 10 s no mesmo enquadramento. O desvio-padrão do
  deslocamento medido é o piso de ruído do método.
- **D2, escala:** filme a régua de 100 mm (ou as marcas da barra) no plano do movimento; 5 medidas na imagem.
- **Cintilação:** filme 10 s de uma região estática/clara com a iluminação do dia; o app (aba Qualidade) mede a
  cintilação. Se a luz for fluorescente, repita com LED DC.
- **Rolling shutter (P3):** uma placa/régua rígida com dois marcadores verticais afastados ≥ 400 px, batida na
  bancada; a diferença de fase entre os marcadores dá o tempo de leitura do sensor.
- **fps real:** anote o modo escolhido no celular (1080p, 240 fps) e **não** use "câmera lenta" com rampa.

## 6. Depois, no PC (ainda no laboratório, se der)

1. Abrir cada vídeo no app, definir ROIs (acelerômetro, parafuso, parede), posição de cada ROI na barra e a
   calibração com o **comprimento correto** (confira o número digitado).
2. Preencher na sessão as massas da seção 1 (mola ⅓ + ferragens) e k₁/k₂ medidos.
3. Rodar, exportar o relatório de cada tomada e **dar push** (como na última vez). Os vídeos ficam fora do git:
   guarde-os e anote nome e tamanho.
4. Me avisar com: tabelas da seção 1, 2 e 4 preenchidas (foto serve) e o arquivo exportado do PULSE.

## O que cada resultado decide

| Se… | Então… |
|---|---|
| k estático ≈ catálogo (±5 %) e massa efetiva ≈ 380 g | modelo fecha; o problema era só massa não modelada |
| k estático bem abaixo do catálogo | atualizar k₁/k₂ na sessão (k de catálogo errado ou fixação flexível) |
| f_n do vídeo e do PULSE iguais na mesma tomada | a diferença de +2 % era entre tomadas; reportar f_n e repetibilidade (3 tomadas) |
| ζ vídeo ≈ ζ PULSE na mesma tomada | a diferença anterior vinha de configuração (amortecedor/pré-carga/tomada) |
| ζ vídeo ≠ ζ PULSE mesmo simultâneos | investigar o método (janela, ROI, taxa) antes de escrever resultado |
| f_n sem acelerômetro ≈ com (dentro de Δf = 1/T) | efeito de massa do acelerômetro não resolvido, como previsto |
