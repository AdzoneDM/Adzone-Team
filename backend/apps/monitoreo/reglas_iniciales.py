"""Reglas de productividad con las que arranca ADZONE. Se ajustan en Monitoreo → Reglas."""
P, N, I = 'P', 'N', 'I'
# (tipo, patrón, categoría) para toda la empresa
GENERALES = [
    # Diseño, video, 3D y producción
    *[('APP', a, P) for a in ['photoshop', 'illustrator', 'indesign', 'premiere', 'afterfx', 'after effects', 'lightroom',
                             'audition', 'resolve', 'capcut', 'blender', 'cinema 4d', 'c4d', 'coreldrw', 'corel', 'figma',
                             'obs64', 'obs', 'vmix', 'adobe media encoder', 'bridge']],
    # Oficina, comunicación de trabajo y desarrollo
    *[('APP', a, P) for a in ['excel', 'winword', 'powerpnt', 'outlook', 'teams', 'zoom', 'code', 'pycharm', 'sublime',
                             'notepad++', 'powershell', 'windowsterminal', 'cmd', 'terminal', 'filezilla', 'putty', 'anydesk',
                             'slack', 'notion', 'acrobat']],
    *[('TITULO', t, P) for t in ['adzone team', 'google docs', 'documentos de google', 'hojas de cálculo', 'google sheets',
                                'presentaciones de google', 'google drive', 'gmail', 'canva', 'figma', 'chatgpt', 'claude',
                                'plesk', 'cpanel', 'vicidial', 'meta business', 'business suite', 'ads manager',
                                'administrador de anuncios', 'google ads', 'analytics', 'trello', 'notion', 'freepik', 'envato',
                                'adobe stock', 'cashflow', 'dgii', 'tss', 'banreservas', 'popular en línea']],
    *[('DOMINIO', d, P) for d in ['adzone.marketing', 'adzone.tv', 'canva.com', 'figma.com', 'docs.google.com', 'drive.google.com',
                                 'business.facebook.com', 'ads.google.com', 'analytics.google.com', 'github.com', 'chatgpt.com', 'claude.ai']],
    # Neutral: navegadores, explorador y utilidades (el título decide)
    *[('APP', a, N) for a in ['explorer', 'finder', 'chrome', 'msedge', 'firefox', 'safari', 'opera', 'brave', 'whatsapp', 'spotify',
                             'calculator', 'systemsettings', 'taskmgr']],
    # Improductivo para la empresa en general
    *[('TITULO', t, I) for t in ['youtube', 'netflix', 'facebook', 'instagram', 'tiktok', 'twitter', 'twitch', 'disney+',
                                'prime video', 'shein', 'temu', 'aliexpress', 'amazon.com', 'mercadolibre', 'juego', 'game',
                                'solitaire', 'candy crush']],
    *[('APP', a, I) for a in ['steam', 'epicgameslauncher', 'roblox', 'minecraft', 'netflix']],
    *[('DOMINIO', d, I) for d in ['youtube.com', 'netflix.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'x.com', 'twitter.com']],
]
# Departamentos donde las redes y YouTube son trabajo
REDES = ['youtube', 'facebook', 'instagram', 'tiktok', 'twitter']
POR_DEPTO = {
    'Marketing': [('TITULO', t, P) for t in REDES] + [('DOMINIO', d, P) for d in ['youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'x.com']],
    'Audiovisual': [('TITULO', t, P) for t in REDES] + [('DOMINIO', d, P) for d in ['youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com']],
    'Adzone TV': [('TITULO', t, P) for t in REDES + ['twitch']] + [('DOMINIO', d, P) for d in ['youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com']],
    'Comercial': [('TITULO', t, P) for t in ['facebook', 'instagram', 'linkedin']],
    'Call Center': [('APP', 'zoiper', P), ('APP', 'microsip', P), ('APP', 'x-lite', P), ('TITULO', 'agent', P), ('TITULO', 'medicare', P)],
}



def sembrar(Regla, Depto):
    """Crea las reglas que falten (no toca las que ya existen ni las cambiadas a mano). Devuelve cuántas creó."""
    creadas = 0
    for tipo, patron, cat in GENERALES:
        _, nueva = Regla.objects.get_or_create(tipo=tipo, patron=patron, departamento=None, defaults={'categoria': cat})
        creadas += nueva
    for nombre, reglas in POR_DEPTO.items():
        depto = Depto.objects.filter(nombre=nombre).first()
        if depto:
            for tipo, patron, cat in reglas:
                _, nueva = Regla.objects.get_or_create(tipo=tipo, patron=patron, departamento=depto, defaults={'categoria': cat})
                creadas += nueva
    return creadas
