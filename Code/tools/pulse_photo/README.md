Scripts exploratórios (rodados em ordem, a partir de um diretório com `img/`):
`crop.py` (recorta os dois gráficos da foto em resolução cheia, que não está no repo) →
`digit_spec.py`, `digit_spec2.py` (grade e pico do espectro) →
`digit_time.py`, `digit_time2.py`, `digit_time3.py` (homografia, envolvente e ajuste exponencial) →
`digit_check.py` (valida a calibração contra os cursores vermelhos do PULSE).
Requer `opencv-python` e `numpy`.
`digit_spec3.py` digitaliza amplitude × frequência do espectro (homografia dos eixos + pico),
e os CSVs finais em `Code/data/acelerometro/` foram gerados a partir de `digit_time3.py`
(envoltória) e `digit_spec3.py` (espectro), com a limpeza descrita no README de lá.
