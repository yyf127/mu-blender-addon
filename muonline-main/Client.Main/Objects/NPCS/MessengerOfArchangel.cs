using Client.Main.Content;
using System.Threading.Tasks;

namespace Client.Main.Objects.NPCS
{
    /// <summary>
    /// Messenger of Archangel NPC - Blood Castle related NPC.
    /// </summary>
    [NpcInfo(233, "Messenger of Archangel")]
    public class MessengerOfArchangel : NPCObject
    {
        public override async Task Load()
        {
            Model = await BMDLoader.Instance.Prepare($"NPC/BloodCastle02.bmd");
            await base.Load();
        }

        protected override void HandleClick()
        {
            var svc = MuGame.Network?.GetCharacterService();
            if (svc != null)
            {
                _ = svc.SendTalkToNpcRequestAsync(NetworkId);
            }
        }
    }
}
