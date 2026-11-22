import Link from "next/link";
import { IconBack } from "@/components/icons";
import { currentUser } from "@/lib/auth";

export const metadata = { title: "О проекте · Мой деканат" };

export default async function AboutPage() {
  const u = await currentUser();
  const back = u ? (u.role === "staff" ? "/staff" : "/") : "/login";
  return (
    <main className="page" style={{ maxWidth: 760, paddingTop: 28, paddingBottom: 48 }}>
      <div className="topbar"><Link href={back} className="pillbtn glass"><IconBack /> {u ? "В кабинет" : "Ко входу"}</Link></div>
      <h1 className="large">О проекте</h1>
      <div className="stack">
        <div className="card">
          <div className="t1">Что это</div>
          <p className="t2 prose">«Мой деканат» — концепт личного кабинета студента для номинации «Вайб-кодинг» MGIMO×AI Challenge 2026, задание «Цифровой деканат будущего». Это не официальный сервис вуза. Все люди, оценки, расписание и положения здесь вымышленные.</p>
        </div>
        <div className="card">
          <div className="t1">Какую проблему решаем</div>
          <p className="t2 prose">Студент узнаёт о переносе пары из чата, о долге — перед сессией, а за справкой стоит в очереди. Информация есть, но она разбросана, и никто не говорит, что делать прямо сейчас.</p>
        </div>
        <div className="card">
          <div className="t1">Что сделано</div>
          <ul className="t2 prose">
            <li>Экран «Сегодня»: ближайшая пара, изменения, риски по учёбе, сроки и статусы заявок.</li>
            <li>Расписание по дням и неделям с отметками переносов и отмен.</li>
            <li>Учёба: баллы, прогноз оценок, причина риска для стипендии и что с этим делать.</li>
            <li>Справки и заявления онлайн, статус по шагам, справка с QR-кодом, которую можно проверить без входа.</li>
            <li>Кабинет учебного офиса: очередь заявок, смена статуса, перенос пар, объявления. Студент сразу получает уведомление.</li>
          </ul>
        </div>
        <div className="card">
          <div className="t1">Что делает ИИ-помощник и чего не делает</div>
          <ul className="t2 prose">
            <li>Отвечает на вопросы по положениям вуза и показывает пункт, на который опирается. Пункт можно раскрыть и прочитать.</li>
            <li>Знает данные только того студента, который вошёл: его расписание, баллы, сроки. На вопрос о чужих данных отвечает отказом.</li>
            <li>Если ответа в положениях нет, говорит «не нашёл», а не выдумывает.</li>
            <li>Черновик заявления собирает код по правилам, а не модель. Отправляет заявление всегда сам студент.</li>
          </ul>
        </div>
        <div className="card">
          <div className="t1">Как мы обращаемся с данными</div>
          <ul className="t2 prose">
            <li>Настоящих персональных данных на сайте нет и вводить их не нужно.</li>
            <li>Пароли хранятся только в виде хэша. Вход держится 7 дней в защищённой cookie.</li>
            <li>Сервер проверяет владельца при каждом запросе: чужую заявку или предмет по ссылке открыть нельзя.</li>
            <li>Демо-данные каждую ночь возвращаются к исходному состоянию, поэтому следы проверок не копятся.</li>
          </ul>
        </div>
        <div className="card">
          <div className="t1">Команда и связь</div>
          <p className="t2 prose">Проект сделан командой участников MGIMO×AI Challenge 2026 вместе с ИИ-ассистентом. Написать команде можно в Telegram: <a href="https://t.me/hfuvo" target="_blank" rel="noopener noreferrer">@hfuvo</a> или <a href="https://t.me/mountaindewcitrus" target="_blank" rel="noopener noreferrer">@mountaindewcitrus</a>.</p>
        </div>
        <p className="concept">Концепт для конкурса · не официальный сервис · данные вымышленные</p>
      </div>
    </main>
  );
}
