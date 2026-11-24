# CustomIcons

Colección de temas de iconos personalizados para KDE Plasma que combinan los **iconos monocromáticos y de interfaz de Breeze / Breeze Dark** (bandeja del sistema, barra lateral de Dolphin, barra lateral de Kickoff, barras de herramientas) con los **iconos a color de carpetas (`places`) y aplicaciones (`apps`)** de distintos temas populares.

## Mapeo de temas

| Tema modificado | Tema / Repositorio original | Base monocromática | URL de origen |
| :--- | :--- | :--- | :--- |
| **Oceano** | Ocean (`ocean-design`) | Breeze Dark | https://invent.kde.org/abetts/ocean-design |
| **Brisus** | Papirus | Breeze | https://github.com/PapirusDevelopmentTeam/papirus-icon-theme |
| **Brisus-Dark** | Papirus-Dark | Breeze Dark | https://github.com/PapirusDevelopmentTeam/papirus-icon-theme |
| **Brisus-Light** | Papirus-Light | Breeze | https://github.com/PapirusDevelopmentTeam/papirus-icon-theme |
| **BrisaSur** | BigSur-icon-theme | Breeze Dark | https://github.com/yeyushengfan258/BigSur-icon-theme |
| **Brisolloid** | Colloid-icon-theme | Breeze Dark | https://github.com/vinceliuice/Colloid-icon-theme |
| **Brisagonal** | Diagonal-icon-theme | Breeze Dark | https://github.com/tamascsabi/Diagonal-icon-theme |
| **Brisatery** | Flatery | Breeze Dark | https://github.com/cbrnix/Flatery |
| **Brisuent** | Fluent-icon-theme | Breeze Dark | https://github.com/vinceliuice/Fluent-icon-theme |
| **Brisatter** | Hatter | Breeze Dark | https://github.com/Mibea/Hatter |
| **Brisajave** | McMojave-circle | Breeze Dark | https://github.com/vinceliuice/McMojave-circle |
| **Brisakos** | Mkos-Big-Sur | Breeze Dark | https://github.com/zayronxio/Mkos-Big-Sur |
| **Brisersal** | Reversal-icon-theme | Breeze Dark | https://github.com/yeyushengfan258/Reversal-icon-theme |
| **Brisela** | Tela-icon-theme | Breeze Dark | https://github.com/vinceliuice/Tela-icon-theme |
| **Brisela-Circle** | Tela-circle-icon-theme | Breeze Dark | https://github.com/vinceliuice/Tela-circle-icon-theme |
| **Brisa10X** | We10X-icon-theme | Breeze Dark | https://github.com/yeyushengfan258/We10X-icon-theme |
| **BrisaWhiteSur** | WhiteSur-icon-theme | Breeze Dark | https://github.com/vinceliuice/WhiteSur-icon-theme |
| **Brisafiro** | Zafiro-icons | Breeze Dark | https://github.com/zayronxio/Zafiro-icons |

## Actualización automática

El script `update_icons.py` verifica si hay nuevos commits en cada repositorio de origen (comparando contra `.theme_sources.json`), descarga únicamente los que tengan cambios, actualiza o agrega los iconos nuevos de carpetas y aplicaciones manteniendo los iconos monocromáticos de Breeze, y regenera la caché con `gtk-update-icon-cache`.

```bash
# Comprobar y aplicar actualizaciones
python3 update_icons.py

# Forzar descarga y reconstrucción de todos los temas
python3 update_icons.py --force
```
