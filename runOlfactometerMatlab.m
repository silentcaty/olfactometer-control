function timingLog = runOlfactometerMatlab(execute, testChannel, testDuration)
%RUNOLFACTOMETERMATLAB Run a reusable 12-channel valve sequence.
%
% Preview only (default; does not open the serial port):
%   runOlfactometerMatlab
%
% Real hardware control:
%   runOlfactometerMatlab(true)
%
% Test only CH1 for 0.5 seconds, ignoring the trials table:
%   runOlfactometerMatlab(true, 1, 0.5)
%
% Tested protocol:
%   115200 baud, 8-N-1, no flow control, one binary uint8 per command.

if nargin < 1
    execute = false;
end
if nargin < 2
    testChannel = [];
end
if nargin < 3
    testDuration = 0.5;
end

validateattributes(execute, {'logical', 'numeric'}, {'scalar'});
execute = logical(execute);

%% ======================= Edit this section =======================

% Leave empty to find one candidate port automatically.
% Mac example: "/dev/cu.usbmodem5ABA1307981"
% Windows example: "COM5"
% If several serial devices are connected, enter the exact port explicitly.
portName = "";

% Confirmed working value for the current instrument.
baudRate = 115200;

% Must not be shorter than 20 ms.
breakInterval = 0.020;

% Each row: [channel, valve-open seconds, wait after trial seconds]
trials = [
    1, 0.5, 1.0;
    2, 0.5, 1.0;
    3, 0.5, 1.0;
    4, 0.5, 1.0;
    5, 0.5, 1.0;
    6, 0.5, 1.0;
    7, 0.5, 1.0;
    8, 0.5, 1.0;
    9, 0.5, 1.0;
    10, 0.5, 1.0;
    11, 0.5, 1.0;
    12, 0.5, 1.0;


];

%% ================================================================

if ~isempty(testChannel)
    validateattributes(testChannel, {'numeric'}, ...
        {'scalar', 'integer', '>=', 1, '<=', 12});
    validateattributes(testDuration, {'numeric'}, ...
        {'scalar', 'finite', 'positive'});
    trials = [testChannel, testDuration, 0];
end

validateattributes(breakInterval, {'numeric'}, ...
    {'scalar', 'finite', '>=', 0.020});
validateattributes(trials, {'numeric'}, ...
    {'2d', 'ncols', 3, 'finite', 'nonnegative'});

channels = trials(:, 1);
if any(channels < 1 | channels > 12 | channels ~= fix(channels))
    error("Trial channel numbers must be integers from 1 to 12.");
end
if any(trials(:, 2) <= 0)
    error("Every valve-open duration must be greater than zero.");
end

% Explicit lookup tables are required because CH10 open is 0x10, not 0x0A.
openCommands = uint8(hex2dec([ ...
    "01", "02", "03", "04", "05", "06", ...
    "07", "08", "09", "10", "11", "12"]));

closeCommands = uint8(hex2dec([ ...
    "21", "22", "23", "24", "25", "26", ...
    "27", "28", "29", "30", "31", "32"]));

allCloseCommand = uint8(hex2dec("6F"));

device = [];
if execute
    if strlength(portName) == 0
        portName = findOlfactometerPort();
    end

    device = serialport( ...
        portName, baudRate, ...
        "DataBits", 8, ...
        "Parity", "none", ...
        "StopBits", 1, ...
        "FlowControl", "none", ...
        "Timeout", 2);
    flush(device);
    fprintf("Connected: %s, %d baud, 8-N-1\n", portName, baudRate);
else
    fprintf("DRY RUN: serial port will not be opened.\n");
end

% This runs on normal exit and most MATLAB errors.
cleanupObject = onCleanup( ...
    @() safeAllClose(device, allCloseCommand, execute)); %#ok<NASGU>

records = repmat(emptyRecord(), 2 + 4 * size(trials, 1), 1);
recordIndex = 0;
timerID = tic;

recordIndex = recordIndex + 1;
records(recordIndex) = sendByte( ...
    device, allCloseCommand, "all-close", NaN, execute, timerID);
waitFor(0.100, execute);

for trialIndex = 1:size(trials, 1)
    channel = trials(trialIndex, 1);
    duration = trials(trialIndex, 2);
    intervalAfter = trials(trialIndex, 3);

    fprintf("\nTrial %d/%d: CH%d open for %.3f s\n", ...
        trialIndex, size(trials, 1), channel, duration);

    recordIndex = recordIndex + 1;
    records(recordIndex) = sendByte( ...
        device, allCloseCommand, "all-close", NaN, execute, timerID);
    waitFor(0.100, execute);

    recordIndex = recordIndex + 1;
    records(recordIndex) = sendByte( ...
        device, openCommands(channel), "open", channel, execute, timerID);
    waitFor(duration, execute);

    recordIndex = recordIndex + 1;
    records(recordIndex) = sendByte( ...
        device, closeCommands(channel), "close", channel, execute, timerID);
    waitFor(breakInterval, execute);

    recordIndex = recordIndex + 1;
    records(recordIndex) = sendByte( ...
        device, allCloseCommand, "all-close", NaN, execute, timerID);
    waitFor(intervalAfter, execute);
end

recordIndex = recordIndex + 1;
records(recordIndex) = sendByte( ...
    device, allCloseCommand, "all-close", NaN, execute, timerID);

timingLog = struct2table(records);

if ~isfolder("logs")
    mkdir("logs");
end
timestamp = string(datetime("now", "Format", "yyyyMMdd_HHmmss"));
logFile = fullfile("logs", "matlab_experiment_" + timestamp + ".csv");
writetable(timingLog, logFile);
fprintf("Log saved: %s\n", logFile);

end


function portName = findOlfactometerPort()
% Select one candidate port on macOS, Windows, or Linux.

ports = serialportlist("available");

if ismac
    candidates = ports(startsWith(ports, "/dev/cu.usbmodem"));
elseif ispc
    candidates = ports(startsWith(upper(ports), "COM"));
else
    candidates = ports( ...
        startsWith(ports, "/dev/ttyACM") | ...
        startsWith(ports, "/dev/ttyUSB"));
end

if isempty(candidates)
    error("No candidate serial port found. Run serialportlist('available').");
end
if numel(candidates) > 1
    fprintf("Candidate ports:\n");
    fprintf("  %s\n", candidates);
    error("Multiple candidates found. Set portName explicitly in the file.");
end

portName = candidates(1);
end


function record = sendByte(device, command, event, channel, execute, timerID)
% Send exactly one binary byte; no text terminator is appended.

before = toc(timerID);
if execute
    write(device, uint8(command), "uint8");
end
after = toc(timerID);

mode = "SEND";
if ~execute
    mode = "DRY RUN";
end

if isnan(channel)
    fprintf("[%s] %s: 0x%02X\n", mode, event, command);
else
    fprintf("[%s] %s CH%d: 0x%02X\n", mode, event, channel, command);
end

record = emptyRecord();
record.event = event;
record.channel = channel;
record.commandHex = sprintf("0x%02X", command);
record.elapsedSeconds = before;
record.writeDurationMs = (after - before) * 1000;
record.executed = execute;
end


function waitFor(seconds, execute)
% Skip waits during preview; wait normally during real control.

if execute
    pause(seconds);
else
    fprintf("[DRY RUN] wait %.3f s\n", seconds);
end
end


function safeAllClose(device, allCloseCommand, execute)
% Best-effort final all-close during normal or error exit.

if ~execute || isempty(device)
    return;
end

try
    write(device, uint8(allCloseCommand), "uint8");
    fprintf("Safety cleanup: sent 0x6F.\n");
catch ME
    warning("Olfactometer:SafeCloseFailed", "%s", ME.message);
end
end


function record = emptyRecord()
record = struct( ...
    "event", "", ...
    "channel", NaN, ...
    "commandHex", "", ...
    "elapsedSeconds", NaN, ...
    "writeDurationMs", NaN, ...
    "executed", false);
end
