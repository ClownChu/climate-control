<h1 align="center">Sensi Control</h1>
<h3 align="center">Allows controlling sensi thermostats</h3>
<h3 align="center">This is a component of <a href=#about-kita>Kita</a></h3>

<br />

<div align="center">
    Connects to Sensi WebSocket to collect information broadcasted by thermostats and execute actions to control the thermostats.
</div>


<hr>

<h2 id="getting-started" align="center">Getting started</h2>
<div>
    <p>Run:</p>
    <ul>
        <li>
            <code>python3 -m venv ./.venv</code>
        </li>
        <li>
            <code>source .venv/bin/activate</code>
        </li>
        <li>
            <code>pip install -r requirements.txt</code>
        </li>
        <li>
            Copy <code>.env.exemple</code> to <code>.env</code> and set <code>REFRESH_TOKEN</code>.
        </li>
        <li>
            <code>python3 ./run.py &lt;profile&gt; &lt;device-id&gt; [refresh-token]</code>
            starts the thermostat, the dashboard at <code>http://127.0.0.1:8099/dashboard</code>, and the repeating Ambient backfill.
        </li>
        <li>
            The refresh token comes from <code>REFRESH_TOKEN</code>. When that is unset, the last argument is used.
        </li>
    </ul>
</div>

<hr>

<h2 align="center" id="weather">Weather dashboard</h2>
<div>
    <p><code>python3 ./run.py &lt;profile&gt; &lt;device-id&gt; [refresh-token]</code> starts the thermostat, the server at <code>http://127.0.0.1:8099/dashboard</code>, and a repeating Ambient backfill. Station uploads are stored as UTC 12-hour JSONL buckets under <code>data/history</code>. Ambient history uses <code>data/ambient</code>. The dashboard charts both. <code>WEATHER_HISTORY_INTERVAL</code> is the pause between backfill passes, in seconds (900 when unset).</p>
    <ul>
        <li>
            <code>python3 -m src.weather.server</code> listens on port 8099. Open <code>http://127.0.0.1:8099/dashboard</code>. Pass a port and a history directory to override the defaults.
        </li>
        <li>
            <code>python3 -m src.weather.history</code> backfills Ambient history into <code>data/ambient</code> until Ctrl-C. It loads <code>AMBIENT_API_KEY</code>, <code>AMBIENT_APPLICATION_KEY</code>, and <code>WEATHER_HISTORY_INTERVAL</code> from <code>.env</code>. <code>AMBIENT_MAC</code> picks one station when the account has several.
        </li>
        <li>
            <code>python3 -m src.weather.server --self-check</code>, <code>python3 -m src.weather.history --self-check</code>, and <code>python3 run.py --self-check</code> exercise the collectors and the supervisor without calling Ambient.
        </li>
    </ul>
</div>

<hr>

<h2 align="center" id="about-kita">About Kita</h2>
<div>
    <code>Kita</code> is a personal assistant developed by <a href="https://www.linkedin.com/in/vitor-de-souza-software"  target="_blank">Vitor de Souza</a> (<a href="htps://github.com/ClownChu" target="_blank">ClownChu</a>). Currently coded in <a href="https://dotnet.microsoft.com" target="_blank">.NET</a>, <a href="https://golang.org" target="_blank">Go</a>, and <a href="https://nodejs.org" target="_blank">Node.js</a>. This personal assistant helps with daily tasks, such as: controlling computers, lights, network, schedules, repetitive tasks, among other features.
</div>

<hr>

<h2 align="center" id="license">License</h2>
<div align="center">
    <a href="https://github.com/ClownChu/sensicontrol" target="_blank">SensiControl source code</a> is made available under the <a href="https://www.gnu.org/licenses/agpl-3.0.en.html" target="_blank">GNU Affero General Public License v3.0</a> license. (<a href="https://choosealicense.com/licenses/agpl-3.0/" target="_blank">Read more</a>)
</div>
