import{lineupSnapshot,moveOrSwap,resetToDraftedPositions,restoreSnapshot,validateDraftArrangement,validateLineup,isLineupEditable}from'../js/lineup.js?v=20260721-minor-tweak-2';import{calculateTeamRatings}from'../js/ratings.js?v=20260721-minor-tweak-2';import{draftRosterView,playerDraftView}from'../js/draft-board.js?v=20260721-minor-tweak-2';import{wheelView}from'../js/wheel.js?v=20260721-minor-tweak-2';import{validatePlayerPositions}from'../js/data-validator.js?v=20260721-minor-tweak-2';

const player=(id,name,positions,ratings={})=>({id,name,teamId:'T',era:'all-time',season:'2000-01',positions,overall:ratings.overall||85,offense:ratings.offense||85,defense:ratings.defense||85,shooting:ratings.shooting||85,playmaking:ratings.playmaking||85,rebounding:ratings.rebounding||85,athleticism:ratings.athleticism||85,active:true});
const makeRoster=()=>[
 {player:player('a','Alpha Guard',['PG','SG'],{playmaking:99,shooting:75,offense:78}),initialAssignedPosition:'PG',assignedPosition:'PG',draftPickNumber:1},
 {player:player('b','Beta Guard',['SG','PG'],{playmaking:76,shooting:99,offense:97}),initialAssignedPosition:'SG',assignedPosition:'SG',draftPickNumber:2},
 {player:player('c','Charlie Wing',['SF','PF']),initialAssignedPosition:'SF',assignedPosition:'SF',draftPickNumber:3},
 {player:player('d','Delta Forward',['PF','SF']),initialAssignedPosition:'PF',assignedPosition:'PF',draftPickNumber:4},
 {player:player('e','Echo Center',['C']),initialAssignedPosition:'C',assignedPosition:'C',draftPickNumber:5}
];
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

export const lineupTests=[
 ['Original drafted lineup is valid',()=>validateLineup(makeRoster()).valid],
 ['Exactly five positions are required',()=>!validateLineup(makeRoster().slice(0,4)).valid],
 ['Duplicate and missing assigned positions are rejected',()=>{const roster=makeRoster();roster[1].assignedPosition='PG';const codes=validateLineup(roster).errors.map(item=>item.code);return codes.includes('DUPLICATE_POSITION')&&codes.includes('MISSING_POSITION')}],
 ['Duplicate players are rejected',()=>{const roster=makeRoster();roster[1].player=roster[0].player;return validateLineup(roster).errors.some(item=>item.code==='DUPLICATE_PLAYER')}],
 ['Unknown and case-mismatched positions are rejected',()=>{const roster=makeRoster();roster[0].assignedPosition='pg';return validateLineup(roster).errors.some(item=>item.code==='UNKNOWN_POSITION')}],
 ['Eligible two-player swap succeeds atomically',()=>{const result=moveOrSwap(makeRoster(),'a','SG');return result.success&&result.roster.find(item=>item.player.id==='a').assignedPosition==='SG'&&result.roster.find(item=>item.player.id==='b').assignedPosition==='PG'}],
 ['Both multi-position players swap successfully',()=>{const result=moveOrSwap(makeRoster(),'c','PF');return result.success&&result.roster.find(item=>item.player.id==='c').assignedPosition==='PF'&&result.roster.find(item=>item.player.id==='d').assignedPosition==='SF'}],
 ['Single-position player cannot move',()=>!moveOrSwap(makeRoster(),'e','PF').success],
 ['Invalid swap leaves the entire lineup unchanged',()=>{const roster=makeRoster(),before=lineupSnapshot(roster),result=moveOrSwap(roster,'a','SF');return !result.success&&same(before,lineupSnapshot(result.roster))}],
 ['Swap fails when destination player cannot return to source',()=>{const roster=makeRoster();roster[1].player.positions=['SG'];return !moveOrSwap(roster,'a','SG').success}],
 ['Eligible move into an empty draft slot succeeds',()=>{const roster=makeRoster().slice(0,1),result=moveOrSwap(roster,'a','SG');return result.success&&result.roster[0].assignedPosition==='SG'&&result.roster[0].initialAssignedPosition==='PG'&&validateDraftArrangement(result.roster).valid}],
 ['Ineligible move into an empty draft slot is atomic',()=>{const roster=makeRoster().slice(0,1),before=lineupSnapshot(roster),result=moveOrSwap(roster,'a','C');return !result.success&&same(before,lineupSnapshot(result.roster))}],
 ['Assigned position changes without overwriting initial position',()=>{const result=moveOrSwap(makeRoster().slice(0,1),'a','SG'),entry=result.roster[0];return entry.initialAssignedPosition==='PG'&&entry.assignedPosition==='SG'&&entry.draftPickNumber===1}],
 ['Draft sidebar keeps draggable players without move controls',()=>{const html=draftRosterView({roster:makeRoster().slice(0,2)},null);return html.includes('draggable="true"')&&!html.includes('draft-position-select')&&!html.includes('draft-move-button')&&!html.includes('<select')}],
 ['Occupied status appears within player details',()=>{const html=draftRosterView({roster:makeRoster().slice(0,1)},null);return html.includes('<small class="occupied-status">Occupied</small>')}],
 ['Lineup feedback remains screen-reader accessible',()=>draftRosterView({roster:makeRoster().slice(0,1)},null).includes('aria-live="polite"')],
 ['Undo snapshot restores the previous valid lineup',()=>{const roster=makeRoster(),snapshot=lineupSnapshot(roster),moved=moveOrSwap(roster,'a','SG').roster;return same(lineupSnapshot(restoreSnapshot(moved,snapshot)),snapshot)}],
 ['Reset restores initial positions and validity',()=>{const moved=moveOrSwap(makeRoster(),'a','SG').roster,reset=resetToDraftedPositions(moved);return reset.validation.valid&&reset.roster.every(item=>item.assignedPosition===item.initialAssignedPosition)}],
 ['Ratings use assigned positions and stay finite',()=>{const roster=makeRoster(),before=calculateTeamRatings(roster),after=calculateTeamRatings(moveOrSwap(roster,'a','SG').roster);return before.positionalFit!==after.positionalFit&&!Object.values(after).some(Number.isNaN)}],
 ['Lineup movement is limited to the draft phase',()=>isLineupEditable('DRAFT')&&!isLineupEditable('REVIEW')&&!isLineupEditable('SEASON')&&!isLineupEditable('PLAYOFF_BRACKET')]
];
lineupTests.push(
 ['One-position player remains restricted',()=>!moveOrSwap([{player:player('single','Single',['C']),initialAssignedPosition:'C',assignedPosition:'C',draftPickNumber:1}],'single','PF').success],
 ['Two-position player can use either listed position',()=>moveOrSwap(makeRoster().slice(0,1),'a','SG').success],
 ['Three-position player can use every listed position',()=>['SG','SF','PF'].every(position=>moveOrSwap([{player:player('three','Three',['SG','SF','PF']),initialAssignedPosition:'SG',assignedPosition:'SG',draftPickNumber:1}],'three',position).success)],
 ['Duplicate and excessive position arrays are invalid',()=>!validatePlayerPositions(['PG','PG']).valid&&!validatePlayerPositions(['PG','SG','SF','PF']).valid],
 ['Three-position eligibility is valid with a warning',()=>{const result=validatePlayerPositions(['SG','SF','PF']);return result.valid&&result.warnings.length>0}],
 ['Clickable card is a semantic non-draggable button',()=>{const p={...player('card','Card Player',['SF','PF']),eligibleOpenPositions:['SF','PF']},html=playerDraftView({players:[p],selectedId:null,eraName:'All-Time',franchiseName:'Boston'});return html.includes('<button type="button" class="player-option')&&!html.includes('draggable=')&&!html.includes('Select Player</button>')}],
 ['Selected card exposes text and aria state',()=>{const p={...player('card','Card Player',['SF','PF']),eligibleOpenPositions:['SF','PF']},html=playerDraftView({players:[p],selectedId:'card',eraName:'All-Time',franchiseName:'Boston'});return html.includes('aria-pressed="true"')&&html.includes('✓ Selected')}],
 ['Unavailable card is disabled with a visible reason',()=>{const p={...player('card','Card Player',['SF']),eligibleOpenPositions:[]},html=playerDraftView({players:[p],selectedId:null,eraName:'All-Time',franchiseName:'Boston'});return html.includes(' disabled')&&html.includes('No eligible open position')}],
 ['Selected player exposes eligible lineup targets without confirmation UI',()=>{const p=player('card','Card Player',['SF','PF']),html=draftRosterView({roster:[]},p);return html.includes('class="roster-slot drop-slot draft-lineup-slot  eligible draft-target"')&&html.includes('Draft Card Player here')&&!html.includes('Confirm Pick')&&!html.includes('draft-assignment-panel')}],
 ['Occupied slots are not new-player draft targets',()=>{const p=player('card','Card Player',['PG','SG']),html=draftRosterView({roster:makeRoster().slice(0,1)},p);return html.includes('Alpha Guard')&&!html.includes('Draft Card Player at PG')&&html.includes('Draft Card Player at SG')}],
 ['Ineligible empty slots remain unavailable',()=>{const p=player('card','Card Player',['SF']),html=draftRosterView({roster:[]},p);return html.includes('This player cannot play here')&&html.includes('Draft Card Player at SF')}],
 ['Drafted lineup entries remain draggable',()=>draftRosterView({roster:makeRoster().slice(0,1)},null).includes('draggable="true"')]
);
lineupTests.push(
 ['Era wheel contains the selected franchise banner above its heading',()=>{const html=wheelView({title:'Era wheel',subtitle:'Choose an Era',items:[],contextLabel:'Boston Celtics'});return html.indexOf('selected-franchise-banner')<html.indexOf('Era wheel')&&html.includes('Boston Celtics')}],
 ['Franchise wheel omits the selected-franchise banner',()=>!wheelView({title:'Franchise wheel',subtitle:'Spin all 30 franchises',items:[]}).includes('selected-franchise-banner')],
 ['Empty slots omit unnecessary availability helper text',()=>{const html=draftRosterView({roster:[]},null);return html.includes('Empty')&&!html.includes('Available for an eligible player')}],
 ['Player list has no search filter sort or clear controls',()=>{const p={...player('card2','Card Two',['SG']),eligibleOpenPositions:['SG']},html=playerDraftView({players:[p],selectedId:null,eraName:'Current',franchiseName:'Boston'});return !html.includes('type="search"')&&!html.includes('player-position-filter')&&!html.includes('player-sort')&&!html.includes('Clear filters')&&html.includes('1 available')}],
 ['Player list preserves supplied natural order',()=>{const a={...player('first','First',['PG']),eligibleOpenPositions:['PG']},b={...player('second','Second',['SG']),eligibleOpenPositions:['SG']},html=playerDraftView({players:[a,b],selectedId:null,eraName:'Current',franchiseName:'Boston'});return html.indexOf('First')<html.indexOf('Second')}]
);
