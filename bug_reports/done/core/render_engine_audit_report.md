# Отчёт о проблемах в `render_engine.py`

**Предложенное имя файла:** `render_engine_audit_report.md`

## Контекст

Файл содержит `RenderEngine` — минимальный Pygame runtime проекта.

Он отвечает за:

```text
pygame.init()
создание display surface
создание clock
создание активного game_screen через screen_factory
главный event/update/draw loop
pygame.quit()
```

Текущая реализация простая и понятная. Она хорошо подходит для раннего прототипа, но на уровне архитектуры runtime уже видны потенциальные ограничения: нет управления жизненным циклом экрана, нет обработки ошибок, нет смены экранов, нет настройки FPS, нет separation между raw pygame events и внутренними input events.

---

# 1. Проблемы файла `render_engine.py`

## 1.1. `screen_factory()` вызывается без передачи созданного display / engine context

### Проблема

В `__init__`:

```python
self.screen = pygame.display.set_mode(screen_size)
pygame.display.set_caption(title)
self.clock = pygame.time.Clock()
self.game_screen = screen_factory()
```

`screen_factory()` вызывается без аргументов.

### Почему это может быть проблемой

Экран может нуждаться в:

- размере окна;
- display surface;
- ссылке на engine;
- resource manager;
- event/input adapter;
- screen manager;
- текущем FPS;
- доступе к runtime config.

Если screen_factory не получает context, экрану придётся искать эти данные глобально или дублировать конфигурацию.

### Рекомендация

Передавать context:

```python
self.game_screen = screen_factory(self)
```

или более безопасно:

```python
self.game_screen = screen_factory(
    screen_size=screen_size,
    display_surface=self.screen,
)
```

Ещё лучше — создать `RenderContext`:

```python
@dataclass
class RenderContext:
    display_surface: pygame.Surface
    screen_size: tuple[int, int]
    clock: pygame.time.Clock
```

---

## 1.2. Нет lifecycle-методов для `game_screen`

### Проблема

Engine сразу вызывает:

```python
self.game_screen.update(dt)
self.game_screen.draw(self.screen)
```

Но не вызывает ничего вроде:

```python
game_screen.start()
game_screen.on_enter()
game_screen.on_exit()
game_screen.shutdown()
```

### Почему это опасно

Экрану может понадобиться:

- загрузить ресурсы;
- подготовить layout после создания display;
- зарегистрировать activities;
- очистить ресурсы при выходе;
- сохранить состояние;
- корректно завершить active activities.

Сейчас всё это должно быть спрятано в `screen_factory()` или в самом `__init__` экрана.

### Рекомендация

Ввести lifecycle:

```python
self.game_screen.start()

...

finally:
    self.game_screen.finish()
    pygame.quit()
```

Минимальный вариант:

```python
if hasattr(self.game_screen, "start"):
    self.game_screen.start()
```

Но лучше сделать это обязательным контрактом экрана.

---

## 1.3. `pygame.quit()` не защищён через `try/finally`

### Проблема

Сейчас:

```python
while running:
    ...
pygame.quit()
```

Если внутри цикла произойдёт exception, `pygame.quit()` не будет вызван.

### Почему это опасно

Окно Pygame может закрыться некорректно, ресурсы могут остаться в странном состоянии, особенно при отладке.

### Рекомендация

Оборачивать run loop:

```python
def run(self):
    try:
        self._run_loop()
    finally:
        pygame.quit()
```

И при наличии screen lifecycle:

```python
finally:
    if hasattr(self.game_screen, "finish"):
        self.game_screen.finish()
    pygame.quit()
```

---

## 1.4. Нет обработки ошибок внутри update/draw loop

### Проблема

Любая ошибка в:

```python
self.game_screen.handle_event(event)
self.game_screen.update(dt)
self.game_screen.draw(self.screen)
```

оборвёт программу.

### Почему это может быть нормально

Для dev-прототипа падение с traceback полезно.

### Почему это может стать проблемой

Если runtime станет более зрелым, может понадобиться:

- логирование crash;
- graceful shutdown;
- сохранение состояния;
- отключение pygame;
- показ debug overlay.

### Рекомендация

Для текущего этапа можно оставить падение.

Но полезно хотя бы обеспечить `finally: pygame.quit()`.

---

## 1.5. FPS жёстко зашит как `60`

### Проблема

```python
dt = self.clock.tick(60) / 1000.0
```

### Почему это ограничивает

FPS нельзя поменять через config.

Для отладки может понадобиться:

- 30 FPS;
- uncapped FPS;
- 120 FPS;
- slow motion;
- stress test.

### Рекомендация

Добавить параметр:

```python
def __init__(..., target_fps=60):
    self.target_fps = target_fps
```

И использовать:

```python
dt = self.clock.tick(self.target_fps) / 1000.0
```

---

## 1.6. `dt` не ограничивается сверху

### Проблема

Если окно зависло, debugger остановил выполнение или система дала лаг, `dt` может стать очень большим:

```python
dt = self.clock.tick(60) / 1000.0
```

### Почему это опасно

Большой `dt` может сломать:

- анимации;
- физику;
- таймеры;
- плавные переходы;
- update logic.

Например animation длительностью `0.12` секунды может мгновенно перескочить в конец.

### Рекомендация

Добавить clamp:

```python
dt = min(self.clock.tick(self.target_fps) / 1000.0, self.max_dt)
```

Например:

```python
self.max_dt = 0.1
```

---

## 1.7. Нет fixed-update или разделения update/render

### Проблема

Сейчас update вызывается один раз на кадр с переменным `dt`:

```python
self.game_screen.update(dt)
self.game_screen.draw(self.screen)
```

### Почему это нормально

Для UI/карточной игры это вполне допустимо.

### Потенциальная проблема

Если появится логика, чувствительная к timestep, переменный `dt` может усложнить поведение.

### Рекомендация

Для текущего проекта можно оставить variable timestep.

Если позже появится физика или точная симуляция, добавить fixed update:

```text
event handling
fixed update N times
draw interpolation
```

---

## 1.8. Нет очистки экрана перед draw

### Проблема

В loop:

```python
self.game_screen.update(dt)
self.game_screen.draw(self.screen)
pygame.display.flip()
```

Engine сам не делает:

```python
self.screen.fill(...)
```

### Почему это может быть нормально

Возможно, `game_screen.draw()` полностью очищает экран.

### Почему это может быть проблемой

Если screen draw не закрашивает весь display, будут оставаться следы прошлых кадров.

### Рекомендация

Зафиксировать контракт:

```text
game_screen.draw(surface) must fully redraw the frame.
```

Или engine должен делать базовую очистку:

```python
self.screen.fill(self.background_color)
self.game_screen.draw(self.screen)
```

Для гибкости можно сделать optional background color.

---

## 1.9. `handle_event()` обязан существовать

### Проблема

В loop:

```python
elif self.game_screen.handle_event(event) is False:
    running = False
```

Если screen не имеет `handle_event`, будет ошибка.

### Почему это может быть нормально

Если `handle_event` — обязательный метод экрана, всё хорошо.

### Рекомендация

Закрепить это через Protocol/interface.

Например:

```python
class GameScreenLike(Protocol):
    def handle_event(self, event: pygame.event.Event) -> bool | None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...
```

---

## 1.10. Семантика `handle_event() is False` может быть неочевидной

### Проблема

```python
elif self.game_screen.handle_event(event) is False:
    running = False
```

Это означает:

```text
если screen.handle_event(event) вернул строго False, закрыть runtime
```

### Почему это может быть проблемой

`False` здесь означает не “event consumed”, а “завершить приложение”.

Но во многих event systems `False` может означать:

```text
событие обработано и дальше не передавать
```

или наоборот:

```text
событие не обработано
```

### Рекомендация

Сделать результат более явным.

Варианты:

```python
result = self.game_screen.handle_event(event)
if result == "quit":
    running = False
```

или:

```python
if self.game_screen.should_quit:
    running = False
```

или enum:

```python
EventResult.CONTINUE
EventResult.QUIT
```

---

## 1.11. Нет преобразования raw pygame events во внутренние input events

### Проблема

Engine отдаёт screen сырой `pygame.event.Event`:

```python
self.game_screen.handle_event(event)
```

### Почему это ограничивает

Внутри screen/activity-слоя придётся знать Pygame API.

Это связывает доменную UI-логику с Pygame:

```text
Activity
-> знает pygame.MOUSEBUTTONDOWN
-> знает pygame координаты
-> знает pygame event fields
```

### Рекомендация

Добавить input adapter:

```python
input_events = self.input_mapper.map_pygame_event(event)
for input_event in input_events:
    self.game_screen.handle_input(input_event)
```

Тогда activities будут работать с project-level input events:

```text
hover
click
double_click
drag_start
drag
drag_end
key
quit
```

---

## 1.12. Нет поддержки смены экранов

### Проблема

Engine хранит один экран:

```python
self.game_screen = screen_factory()
```

И дальше работает только с ним.

### Почему это нормально

Для одного sandbox screen этого достаточно.

### Почему это станет проблемой

Для игры могут понадобиться:

- menu screen;
- table screen;
- pause screen;
- settings screen;
- loading screen;
- debug screen.

### Рекомендация

Ввести screen manager:

```python
self.screen_manager = ScreenManager(initial_screen)
```

И в loop:

```python
self.screen_manager.handle_event(event)
self.screen_manager.update(dt)
self.screen_manager.draw(self.screen)
```

---

## 1.13. Нет resize handling

### Проблема

Display создаётся так:

```python
pygame.display.set_mode(screen_size)
```

Без flags и без обработки `VIDEORESIZE`.

### Почему это может быть нормально

Если окно фиксированного размера — всё хорошо.

### Почему это может стать проблемой

Если понадобится resize:

- frame layout должен пересчитываться;
- play area должна обновляться;
- card slots должны пересчитывать позиции;
- screen size должен обновиться в context.

### Рекомендация

Если resize не нужен — явно считать окно fixed-size.

Если нужен — добавить:

```python
pygame.RESIZABLE
```

и обработку resize event.

---

## 1.14. Нет fullscreen / vsync / flags

### Проблема

```python
pygame.display.set_mode(screen_size)
```

использует дефолтные flags.

### Почему это не критично

Для прототипа нормально.

### Рекомендация

Добавить optional параметры:

```python
display_flags=0
vsync=0
```

В Pygame 2 можно использовать:

```python
pygame.display.set_mode(screen_size, flags=display_flags, vsync=vsync)
```

---

## 1.15. Нет настройки caption/icon после старта

### Проблема

Caption задаётся только один раз:

```python
pygame.display.set_caption(title)
```

### Почему это незначительно

Для sandbox достаточно.

### Возможное улучшение

Позже можно добавить:

```python
set_title()
set_icon()
```

---

## 1.16. Нет ограничения ответственности между Engine и GameScreen

### Проблема

Сейчас не описано, кто отвечает за:

- очистку экрана;
- обработку quit;
- смену screen;
- lifecycle;
- input mapping;
- resource cleanup.

### Почему это важно

Когда проект растёт, нужно чётко знать:

```text
RenderEngine отвечает за Pygame runtime и loop.
GameScreen отвечает за игровую сцену.
Activity отвечает за локальные режимы поведения.
```

### Рекомендация

Добавить краткий контракт в docstring `RenderEngine`.

---

# 2. Обобщение архитектурных проблем runtime-подхода

## 2.1. Engine слишком минимален для растущей Activity-архитектуры

Текущий engine хороший для первого запуска:

```text
events
update
draw
flip
```

Но уже существующие Activity-классы требуют более зрелой инфраструктуры:

- lifecycle;
- screen manager;
- input mapping;
- activity cleanup;
- animation cleanup;
- layout invalidation;
- screen resize handling.

### Рекомендация

Не обязательно усложнять engine сразу, но нужно определить roadmap:

```text
RenderEngine
-> ScreenManager
-> InputMapper
-> ActivityManager
-> AnimationManager
```

---

## 2.2. Raw Pygame events протекают слишком глубоко

Если `game_screen.handle_event()` дальше прокидывает raw Pygame events в Activity, то Activity-слой становится зависим от Pygame.

### Рекомендация

Ввести project input events:

```python
@dataclass
class InputEvent:
    type: str
    screen_pos: tuple[int, int] | None = None
    button: str | None = None
    key: str | None = None
```

И adapter:

```text
pygame event -> InputEvent
```

Тогда можно проще тестировать Activity без Pygame.

---

## 2.3. Нет центрального управления lifecycle

Сейчас каждая Activity сама решает:

```text
если не started — start
```

И сама запускает вложенные activity.

Engine же просто вызывает:

```python
game_screen.update(dt)
```

### Риск

Lifecycle размазывается по всей системе.

### Рекомендация

Постепенно перейти к manager-подходу:

```python
activity_manager.update(dt)
activity_manager.finish_removed()
animation_manager.update(dt)
layout_manager.update_dirty()
```

Даже если GameScreen остаётся владельцем этих manager-ов, сам принцип должен быть единым.

---

## 2.4. Нет единого shutdown pipeline

Когда приложение завершается, сейчас вызывается только:

```python
pygame.quit()
```

Но в проекте уже есть объекты, которым может понадобиться cleanup:

- active activities;
- generated groups;
- slot frames;
- animations;
- resource manager;
- debug overlays;
- temporary fixtures.

### Рекомендация

Добавить shutdown:

```python
def shutdown(self):
    self.game_screen.finish()
    self.resource_manager.close()
    pygame.quit()
```

И вызывать его через `finally`.

---

## 2.5. Нет центрального места для dt policy

Сейчас dt берётся прямо в run loop.

Но animation system и activity system чувствительны к dt.

### Рекомендация

Ввести runtime config:

```python
target_fps = 60
max_dt = 0.1
time_scale = 1.0
```

И использовать:

```python
dt = min(raw_dt, max_dt) * time_scale
```

Это будет полезно для slow motion/debug.

---

# 3. Приоритет исправлений

## Высокий приоритет

1. Обернуть loop в `try/finally`, чтобы `pygame.quit()` вызывался всегда.
2. Добавить lifecycle для `game_screen`: `start()` и `finish()` / `shutdown()`.
3. Сделать семантику выхода из `handle_event()` явной, а не через `is False`.
4. Добавить `target_fps` и `max_dt`.
5. Зафиксировать контракт: кто очищает экран — engine или game_screen.

## Средний приоритет

6. Передавать context в `screen_factory`.
7. Добавить input adapter: `pygame.Event -> project InputEvent`.
8. Ввести screen manager, если появится больше одного экрана.
9. Добавить resize policy: fixed-size или resizable.
10. Добавить Protocol/type hints для `GameScreen`.

## Низкий приоритет

11. Добавить display flags / vsync.
12. Добавить настройку title/icon через методы.
13. Добавить error logging.
14. Поддержать pause/time_scale.
15. Разделить `_run_loop()` и публичный `run()`.

---

# 4. Возможный улучшенный каркас

Минимальный более устойчивый вариант:

```python
class RenderEngine:
    def __init__(
        self,
        screen_factory,
        screen_size=(800, 600),
        title="Sandbox",
        target_fps=60,
        max_dt=0.1,
        background_color=None,
    ):
        pygame.init()
        self.display_surface = pygame.display.set_mode(screen_size)
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.target_fps = target_fps
        self.max_dt = max_dt
        self.background_color = background_color
        self.game_screen = screen_factory(self)

    def run(self):
        try:
            if hasattr(self.game_screen, "start"):
                self.game_screen.start()

            self._run_loop()
        finally:
            if hasattr(self.game_screen, "finish"):
                self.game_screen.finish()
            pygame.quit()

    def _run_loop(self):
        running = True
        while running:
            raw_dt = self.clock.tick(self.target_fps) / 1000.0
            dt = min(raw_dt, self.max_dt)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break

                result = self.game_screen.handle_event(event)
                if result == "quit":
                    running = False
                    break

            self.game_screen.update(dt)

            if self.background_color is not None:
                self.display_surface.fill(self.background_color)

            self.game_screen.draw(self.display_surface)
            pygame.display.flip()
```

Это не финальная архитектура, но уже лучше фиксирует:

- lifecycle;
- guaranteed cleanup;
- FPS config;
- max dt;
- context passing;
- явную семантику выхода.

---

# 5. Главный вывод

`render_engine.py` сейчас является хорошим минимальным Pygame runner-ом:

```text
init
event loop
update
draw
flip
quit
```

Но остальная архитектура проекта уже растёт в сторону сложной Activity-системы. Для такой системы текущий engine слишком минимален.

Главные следующие шаги:

```text
1. гарантированный shutdown через try/finally
2. lifecycle game_screen
3. явный input contract
4. target_fps / max_dt
5. screen/context contract
```

Самое важное — не дать Pygame-specific деталям и raw event-ам протечь слишком глубоко в Activity-слой. Engine должен быть границей между Pygame runtime и внутренней архитектурой проекта.
