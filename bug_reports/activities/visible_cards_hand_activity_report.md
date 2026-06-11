# Code Review Report: `visible_cards_hand_activity(3).py`

## 1. Назначение файла

`VisibleCardsHandDecorator` — это декоратор над activity руки, который подменяет визуальные ресурсы закрытых/сгенерированных карт на конкретные видимые карты.

Класс отвечает за:

- хранение списка `card_resource_keys`;
- ограничение количества отображаемых карт через `max_cards`;
- настройку оборачиваемой `hand_activity` через `configure_card_resources()`;
- передачу `start/update/draw/finish` во внутреннюю activity;
- применение fixture с видимыми картами;
- предоставление selection context для контроллера.

Идея класса хорошая: геометрия руки остается в `hand_activity`, а список конкретных карт — в декораторе.

---

## 2. Главные проблемы

### 2.1. Слишком жесткий контракт `validate_hand_activity()`

```python
required_methods = (
    "start",
    "update",
    "draw",
    "apply_fixture",
    "clear_generated_groups",
    "sync_visual_groups",
    "apply_fan_layout",
    "is_finished",
    "finish",
    "configure_card_resources",
)
```

Проблема: декоратор требует от `hand_activity` очень много конкретных методов. Это делает его сильно связанным с текущей реализацией `BotHandActivity`/`PlayerHandActivity`.

Риск: если появится другая реализация руки, которая умеет отображать карты, но не имеет, например, `apply_fixture()` или `draw()`, она не пройдет валидацию, хотя могла бы работать.

Рекомендация:

- разделить обязательный runtime-контракт и dev/debug-контракт;
- `apply_fixture()` и `draw()` сделать опциональными;
- явно описать protocol/interface для hand activity.

Возможный минимальный обязательный контракт:

```python
required_methods = (
    "start",
    "update",
    "finish",
    "configure_card_resources",
    "clear_generated_groups",
    "sync_visual_groups",
    "apply_fan_layout",
)
```

`draw`, `apply_fixture`, `is_finished` можно проверять там, где они реально вызываются.

---

### 2.2. `update()` не делает `return` после автостарта

```python
def update(self, dt):
    if not self.started:
        self.start()
    self.hand_activity.update(dt)
```

Если activity еще не стартовала, `start()` уже может вызвать `hand_activity.start()`. После этого в том же кадре сразу вызывается `hand_activity.update(dt)`.

Это не обязательно баг, но может приводить к двойной работе в первый кадр, если `hand_activity.start()` уже делает синхронизацию и layout.

В похожих классах проекта часто используется паттерн:

```python
if not self.started:
    self.start()
    return
```

Рекомендация: привести поведение к единому стилю с остальными activity.

---

### 2.3. `set_cards()` всегда полностью пересоздает группы

```python
self.hand_activity.clear_generated_groups()
self.card_resource_keys = next_keys
self.configure_hand_activity()
```

Даже если изменился один ресурс карты, все visual groups удаляются и создаются заново.

Риск:

- сбрасываются hover/selection состояния;
- могут сбрасываться анимации;
- возможны визуальные скачки;
- лишняя работа при частых обновлениях руки.

Сейчас это допустимо для простой реализации, но для интерактивной руки лучше иметь более мягкий sync.

Рекомендация:

- для первого этапа оставить как есть, но явно пометить как простую стратегию;
- позже заменить на diff-обновление: удалять/добавлять только изменившиеся слоты.

---

### 2.4. `get_card_resource_key()` бросает `RuntimeError` при выходе за диапазон

```python
if index < 0 or index >= len(self.card_resource_keys):
    raise RuntimeError("VisibleCardsHandDecorator card index is out of range")
```

Это может быть правильно как жесткая защита инварианта. Но здесь важно понимать: этот метод передается в `hand_activity` как provider.

Если `hand_activity` в какой-то момент запросит resource key для индекса, который уже устарел после изменения количества карт, приложение упадет.

Рекомендация:

- оставить исключение, если это считается нарушением инварианта;
- но сообщение сделать более диагностическим:

```python
raise RuntimeError(
    f"Card index out of range: index={index}, cards={len(self.card_resource_keys)}"
)
```

---

### 2.5. `finish()` может финишировать уже завершенную `hand_activity`

```python
def finish(self):
    if self.owns_hand_activity:
        self.hand_activity.finish()
    super().finish()
```

В `PlayerTurnActivity` уже есть более осторожный вариант: сначала проверяется `is_finished()`.

Риск небольшой, но если `finish()` внутренней activity не идемпотентен, возможны повторные удаления групп или побочные эффекты.

Рекомендация:

```python
def finish(self):
    if self.owns_hand_activity:
        is_finished = getattr(self.hand_activity, "is_finished", None)
        if not callable(is_finished) or not is_finished():
            self.hand_activity.finish()
    super().finish()
```

---

## 3. Средние проблемы

### 3.1. `is_finished()` зависит от внутренней activity

```python
return self._finished or self.hand_activity.is_finished()
```

Это логично, но есть тонкость: декоратор может считаться завершенным, если завершилась внутренняя activity, даже если сам декоратор не проходил `finish()`.

Риск: внешний код может увидеть `is_finished() == True`, но ресурсы/состояние декоратора еще не очищены.

Рекомендация: решить архитектурно, кто является владельцем жизненного цикла:

- если декоратор полностью владеет рукой, то завершение внутренней activity должно завершать декоратор;
- если не владеет, возможно, `is_finished()` должен возвращать только `self._finished`.

---

### 3.2. `apply_fixture()` смешивает fixture карт и fixture геометрии

```python
cards = self.get_fixture_cards(fixture)
...
decorated_fixture = dict(fixture)
decorated_fixture["card_count"] = len(self.card_resource_keys)
decorated_fixture.pop("resource_key", None)
self.hand_activity.apply_fixture(decorated_fixture)
```

Код работает, но fixture становится смешанным объектом: часть полей относится к visible cards, часть — к геометрии руки.

Риск: по мере роста debug/dev fixture будет сложнее понимать, какие поля кто обрабатывает.

Рекомендация:

- в будущем разделить fixture на секции:

```python
{
    "cards": [...],
    "hand": {
        "scale_factor": 0.8,
        "center_offset": [50, 0]
    }
}
```

Пока можно оставить текущую форму, но задокументировать, что `resource_key` намеренно удаляется.

---

### 3.3. `get_manifest_card_keys()` завязан на строковые правила ресурсов

```python
if key.startswith("cards.") and key != "cards.card_back"
```

Это удобно для временного debug GUI, но такая логика плохо масштабируется.

Риск: если структура manifest изменится, декоратор перестанет корректно выбирать карты.

Рекомендация:

- оставить только как dev helper;
- не использовать в controller/runtime path;
- лучше вынести фильтр в `resource_manager` или manifest API.

---

### 3.4. `get_card_selection_context()` подменяет `card_id` на `resource_key`

```python
context["card_id"] = resource_key
context["resource_key"] = resource_key
```

Это удобно на текущем этапе, но архитектурно `card_id` и `resource_key` — разные сущности.

Риск: когда появятся реальные игровые карты, `card_id` должен быть ID игровой сущности, а не путь к ресурсу.

Рекомендация:

- сейчас допустимо как временная заглушка;
- добавить TODO или явно назвать это временным поведением;
- позже хранить карточные дескрипторы вида:

```python
{
    "card_id": "game-card-123",
    "resource_key": "cards.ace_spades"
}
```

---

## 4. Мелкие замечания

### 4.1. `resource_manager` нужен только для `cards_from_manifest`

В обычном режиме `resource_manager` не используется самим декоратором. Это нормально, но можно явно отразить в docstring.

---

### 4.2. `normalize_cards()` принимает только `str` и `dict`

```python
elif isinstance(card, dict):
    resource_key = card.get("resource_key") or card.get("key")
```

Если в будущем появится полноценная модель карты, этот метод придется расширять.

Рекомендация: заранее не усложнять, но не смешивать `resource_key` и `card_id`.

---

### 4.3. `normalize_slice()` принимает tuple/list/dict, но не `slice`

Название намекает на slice, но объект Python `slice` не поддерживается.

Это не баг, но можно либо добавить поддержку `slice`, либо переименовать ожидание в документации fixture.

---

## 5. Приоритет исправлений

### Высокий приоритет

1. Уточнить контракт `validate_hand_activity()`.
2. Привести `update()` к единому паттерну `start(); return`.
3. Развести понятия `card_id` и `resource_key` до того, как появится реальный controller-driven hand.

### Средний приоритет

4. Сделать `finish()` безопаснее при повторном вызове.
5. Добавить более диагностическое сообщение в `get_card_resource_key()`.
6. Задокументировать, что `get_manifest_card_keys()` — временный debug source.

### Низкий приоритет

7. Поддержать `slice` в `normalize_slice()` или уточнить формат fixture.
8. Подумать о diff-обновлении карт вместо полного `clear_generated_groups()`.

---

## 6. Рекомендуемый минимальный патч

```python
def update(self, dt):
    if not self.started:
        self.start()
        return
    self.hand_activity.update(dt)
```

```python
def get_card_resource_key(self, index):
    if index < 0 or index >= len(self.card_resource_keys):
        raise RuntimeError(
            f"VisibleCardsHandDecorator card index is out of range: "
            f"index={index}, cards={len(self.card_resource_keys)}"
        )
    return self.card_resource_keys[index]
```

```python
def finish(self):
    if self.owns_hand_activity:
        is_finished = getattr(self.hand_activity, "is_finished", None)
        if not callable(is_finished) or not is_finished():
            self.hand_activity.finish()
    super().finish()
```

---

## 7. Итог

`VisibleCardsHandDecorator` — полезный слой, который правильно отделяет список видимых карт от геометрии руки. Главная архитектурная ценность класса в том, что он позволяет переиспользовать одну и ту же fan-layout activity для разных наборов карт.

Основные риски сейчас:

1. слишком жесткая зависимость от конкретной реализации `hand_activity`;
2. смешение `card_id` и `resource_key`;
3. полное пересоздание visual groups при любом изменении карт;
4. неидеально согласованный жизненный цикл `start/update/finish`.

Самое важное перед дальнейшим развитием — зафиксировать контракт между декоратором, hand activity и controller. Особенно важно не дать `resource_key` превратиться в постоянную замену настоящего игрового `card_id`.
